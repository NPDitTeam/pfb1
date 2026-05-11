# -*- coding: utf-8 -*-
"""
VAT Calculate From Total - Account Move Override v2.1.0

Hybrid mode — ORM hook สั้นๆ + SQL line-level fix
แก้ปัญหา bi recompute ตอน post invoice / รับชำระ ทำยอด drift จาก Method A

ฟังก์ชันหลัก:
    0. _compute_amount override (lightweight): super → ORM-assign 3 ฟิลด์
       amount_untaxed/amount_tax/amount_total ทับค่าจาก bi
       (bi @api.depends ไม่มี 3 ฟิลด์นี้ → ปลอดภัย ไม่ trigger cascade)
       *** ห้ามแตะ discount_amt_line / amount_price_subtotal_without_discount
           เพราะคือต้นเหตุ -0.09 drift ใน v1.x ***
    1. create() / write() → เรียก _fix_tax_lines_in_db (เฉพาะ draft)
    2. action_post() → flush + _fix_tax_lines_in_db_posted_safe (post กัน edge case)
    3. _fix_tax_lines_in_db: SQL UPDATE
        - account_move_line: tax line + expense rounding + counterpart
        - account_move: amount_untaxed/tax/total
        - account_move: amount_price_subtotal_without_discount + discount_amt_line=0
        - account_move: amount_price_total_full
        - account_move_tax_invoice (l10n_th) ถ้ามี

หมายเหตุ MRO:
    vat_from_total.depends = [..., 'npd_rent_price_round'] → vat_from_total
    inherit ทีหลัง → create/write/_compute_amount ของ vat_from_total ครอบ
    npd_rent_price_round + bi → ORM/SQL ของเราเป็นชั้นสุดท้ายที่เขียน DB
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

INVOICE_TYPES = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')


class AccountMove(models.Model):
    _inherit = 'account.move'

    vat_calculation_method = fields.Selection([
        ('from_total', 'คำนวณจากยอดรวม (From Total)'),
        ('per_line', 'คำนวณทีละบรรทัด (Per Line)'),
    ], string='วิธีคำนวณ VAT', default='from_total',
       help='From Total: ถอด VAT จากยอดรวมทั้งหมดครั้งเดียว\n'
            'Per Line: ถอด VAT ทีละบรรทัดแล้วรวม (ปัดเศษแต่ละบรรทัด)')

    # =====================================================================
    # 0) _compute_amount override (lightweight ORM hook)
    # =====================================================================
    # ทำไมต้องมี: bi_sale_purchase_discount_with_tax มี _compute_amount ที่
    # ผูกกับ @api.depends ของ line.balance / payment / reconcile / etc.
    # ทุกครั้งที่ trigger ฟัยร์ (เช่น ตอน post invoice หรือรับชำระ) bi จะ
    # recompute amount_untaxed/total ใหม่จาก formula:
    #     amount_untaxed = amount_price_subtotal_without_discount - discount_amt_line
    # ซึ่งใช้ค่าที่ npd_rent_price_round (Method A) ตั้งไว้บน line ทำให้
    # ออก subtotal_without_discount ไม่เท่ากับ from-total → ยอดเลื่อน
    #
    # วิธีแก้: hook ที่ end ของ chain (vat_from_total เป็น MRO ตัวสุดท้าย)
    # super() แล้ว ORM-assign target values ของ from-total ทับเฉพาะ 3 ฟิลด์
    # bi @api.depends ไม่มี amount_untaxed/amount_tax/amount_total เป็น
    # dependency ของ compute ตัวอื่น → ไม่ trigger cascade กลับ
    #
    # หมายเหตุสำคัญ: ห้ามแตะ discount_amt_line / amount_price_subtotal_without_discount
    # เพราะการเขียนทับสองตัวนี้คือต้นเหตุของ -0.09 drift ใน v1.x
    @api.depends('vat_calculation_method')
    def _compute_amount(self):
        super(AccountMove, self)._compute_amount()
        for move in self:
            if move.move_type not in INVOICE_TYPES:
                continue
            full = move._calc_target_taxes_full()
            if not full:
                continue
            currency = move.currency_id or move.company_id.currency_id

            target_untaxed = currency.round(
                sum(v['untaxed'] for v in full.values())
            )
            target_tax = currency.round(
                sum(v['tax'] for v in full.values())
            )

            # บวก lines ที่ไม่มี tax
            inv_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type not in ('line_section', 'line_note')
            )
            no_tax_amt = sum(
                move._get_line_effective_amount(l, currency)
                for l in inv_lines if not l.tax_ids
            )
            target_untaxed = currency.round(target_untaxed + no_tax_amt)
            target_total = currency.round(target_untaxed + target_tax)

            # ORM assign — ทับค่าจาก bi เฉพาะ 3 ฟิลด์ totals
            # (ไม่แตะ bi fields เพื่อกัน feedback drift)
            if currency.compare_amounts(move.amount_untaxed, target_untaxed) != 0:
                move.amount_untaxed = target_untaxed
            if currency.compare_amounts(move.amount_tax, target_tax) != 0:
                move.amount_tax = target_tax
            if currency.compare_amounts(move.amount_total, target_total) != 0:
                move.amount_total = target_total

    # =====================================================================
    # 1) create: หลังสร้าง → SQL fix (line balance + l10n_th)
    # =====================================================================
    @api.model_create_multi
    def create(self, vals_list):
        moves = super(AccountMove, self).create(vals_list)
        for move in moves:
            if (move.move_type in INVOICE_TYPES
                    and move.state == 'draft'
                    and not self.env.context.get('_vat_fixing')):
                move.with_context(_vat_fixing=True)._fix_tax_lines_in_db()
        return moves

    # =====================================================================
    # 2) write: หลังแก้ไข → SQL fix
    # =====================================================================
    def write(self, vals):
        res = super(AccountMove, self).write(vals)

        # เฉพาะเมื่อมีการเปลี่ยน line_ids/invoice_line_ids/term/method
        trigger_keys = {'line_ids', 'invoice_line_ids',
                        'invoice_payment_term_id', 'vat_calculation_method'}
        if (trigger_keys & set(vals.keys())
                and not self.env.context.get('_vat_fixing')):
            for move in self:
                if (move.move_type in INVOICE_TYPES
                        and move.state == 'draft'):
                    move.with_context(
                        _vat_fixing=True
                    )._fix_tax_lines_in_db()
        return res

    # =====================================================================
    # 3) action_post: หลัง post → re-fix line balance อีกรอบ (กัน edge case)
    # =====================================================================
    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self:
            if (move.move_type in INVOICE_TYPES
                    and not self.env.context.get('_vat_fixing')):
                # บังคับ flush ค่าจาก _compute_amount override ลง DB ก่อน
                # แล้วยืนยัน line balance ให้ตรงกับยอด from-total
                move.flush()
                move.with_context(_vat_fixing=True)._fix_tax_lines_in_db_posted_safe()
        return res

    def _fix_tax_lines_in_db_posted_safe(self):
        """
        Wrapper: เรียก _fix_tax_lines_in_db ได้แม้ state='posted'
        (ไม่ค้ำ check_balanced ซ้ำ — เพราะ super().action_post() ทำไปแล้ว)
        """
        self.ensure_one()
        # คงพฤติกรรมเดิมของ _fix_tax_lines_in_db ที่อ่าน DB ปัจจุบัน
        # → SQL update ทับ (ไม่ปฏิเสธเพราะ state)
        self._fix_tax_lines_in_db()

    # =====================================================================
    # Core: SQL-only fix (no ORM cascade)
    # =====================================================================
    def _fix_tax_lines_in_db(self):
        """
        SQL UPDATE แบบครบทั้ง 3 ระดับ:
            1. account_move_line: tax line + expense rounding + counterpart
            2. account_move_tax_invoice (l10n_th): sync balance ตาม tax line
            3. account_move: amount_* + bi fields (ตัดวงจร bi recompute drift)

        ไม่เรียก ORM write/compute ใดๆ — ป้องกัน chain trigger กลับมาทับ
        """
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id

        full = self._calc_target_taxes_full()
        if not full:
            return

        # === คำนวณยอด target (untaxed/tax/total) ===
        target_untaxed = currency.round(
            sum(v['untaxed'] for v in full.values())
        )
        target_tax = currency.round(
            sum(v['tax'] for v in full.values())
        )

        # บวก lines ที่ไม่มี tax เข้า untaxed
        inv_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )
        no_tax_amt = sum(
            self._get_line_effective_amount(l, currency)
            for l in inv_lines if not l.tax_ids
        )
        target_untaxed = currency.round(target_untaxed + no_tax_amt)
        target_total = currency.round(target_untaxed + target_tax)

        target_per_tax = {tid: v['tax'] for tid, v in full.items()}

        cr = self.env.cr
        updates = []  # [(id, new_debit, new_credit, new_amount_currency)]
        total_diff = 0.0

        # === 1) ปรับ tax journal line ===
        for tax_id, tax_amt in target_per_tax.items():
            cr.execute("""
                SELECT id, debit, credit, amount_currency
                FROM account_move_line
                WHERE move_id = %s
                  AND tax_repartition_line_id IN (
                      SELECT id FROM account_tax_repartition_line
                      WHERE invoice_tax_id = %s
                         OR refund_tax_id = %s
                  )
            """, (self.id, tax_id, tax_id))
            rows = cr.fetchall()
            if not rows:
                continue

            current_tax = abs(sum(
                (r[1] or 0.0) - (r[2] or 0.0) for r in rows
            ))
            diff = currency.round(tax_amt - current_tax)
            if currency.is_zero(diff):
                continue

            row = rows[0]  # (id, debit, credit, amount_currency)
            line_id, deb, cred, amt_cur = row
            if deb:
                new_deb = currency.round(deb + diff)
                new_cred = cred
            else:
                new_deb = deb
                new_cred = currency.round(cred + diff)

            if (amt_cur or 0.0) >= 0:
                new_amt = currency.round((amt_cur or 0.0) + diff)
            else:
                new_amt = currency.round((amt_cur or 0.0) - diff)

            updates.append((line_id, new_deb, new_cred, new_amt))
            total_diff += diff

            _logger.info(
                'VAT From Total [%s] tax: %s %.2f->%.2f',
                self.name or 'Draft', tax_id,
                current_tax, tax_amt,
            )

        # === 2) ปรับ expense/revenue line สุดท้าย (rounding diff) ===
        cr.execute("""
            SELECT id, debit, credit, amount_currency
            FROM account_move_line
            WHERE move_id = %s
              AND tax_repartition_line_id IS NULL
              AND account_id NOT IN (
                  SELECT id FROM account_account
                  WHERE internal_type IN ('receivable', 'payable')
              )
              AND (display_type IS NULL
                   OR display_type NOT IN
                   ('line_section', 'line_note'))
              AND (exclude_from_invoice_tab IS NULL
                   OR exclude_from_invoice_tab = false)
            ORDER BY id
        """, (self.id,))
        exp_rows = cr.fetchall()

        if exp_rows:
            current_untaxed = abs(sum(
                (r[1] or 0.0) - (r[2] or 0.0) for r in exp_rows
            ))
            u_diff = currency.round(target_untaxed - current_untaxed)

            if not currency.is_zero(u_diff):
                last = exp_rows[-1]
                lid, deb, cred, amt_cur = last
                if deb:
                    new_deb = currency.round(deb + u_diff)
                    new_cred = cred
                else:
                    new_deb = deb
                    new_cred = currency.round(cred + u_diff)
                if (amt_cur or 0.0) >= 0:
                    new_amt = currency.round((amt_cur or 0.0) + u_diff)
                else:
                    new_amt = currency.round((amt_cur or 0.0) - u_diff)

                updates.append((lid, new_deb, new_cred, new_amt))
                total_diff += u_diff

                _logger.info(
                    'VAT From Total [%s] expense adj: %.2f',
                    self.name or 'Draft', u_diff,
                )

        # === 3) ปรับ counterpart (receivable/payable) ===
        if not currency.is_zero(total_diff):
            cr.execute("""
                SELECT id, debit, credit, amount_currency
                FROM account_move_line
                WHERE move_id = %s
                  AND account_id IN (
                      SELECT id FROM account_account
                      WHERE internal_type IN ('receivable', 'payable')
                  )
                LIMIT 1
            """, (self.id,))
            cp_row = cr.fetchone()

            if cp_row:
                lid, deb, cred, amt_cur = cp_row
                if cred:
                    new_deb = deb
                    new_cred = currency.round(cred + total_diff)
                    new_amt = currency.round(
                        (amt_cur or 0.0) - total_diff)
                else:
                    new_deb = currency.round(deb + total_diff)
                    new_cred = cred
                    new_amt = currency.round(
                        (amt_cur or 0.0) + total_diff)

                updates.append((lid, new_deb, new_cred, new_amt))

        # === Execute SQL line updates ===
        # สำหรับ same currency: amount_currency = balance = debit - credit
        same_currency = (
            (self.currency_id or self.company_id.currency_id)
            == self.company_id.currency_id
        )

        if updates:
            # ตรวจว่า l10n_th_tax_invoice ติดตั้งหรือไม่
            cr.execute("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'account_move_tax_invoice'
            """)
            has_tax_invoice = bool(cr.fetchone())

            for (lid, new_deb, new_cred, new_amt) in updates:
                new_balance = (new_deb or 0.0) - (new_cred or 0.0)
                final_amt = new_balance if same_currency else new_amt

                cr.execute("""
                    UPDATE account_move_line
                    SET debit = %s,
                        credit = %s,
                        balance = %s,
                        amount_currency = %s
                    WHERE id = %s
                """, (new_deb, new_cred,
                      new_balance, final_amt, lid))

                # === Sync l10n_th_tax_invoice ===
                if has_tax_invoice:
                    cr.execute("""
                        UPDATE account_move_tax_invoice
                        SET balance = SIGN(COALESCE(balance, 1)) * ABS(%s)
                        WHERE move_line_id = %s
                    """, (new_balance, lid))

        # === 4) SQL UPDATE account_move totals ===
        # ทับยอดรวมของ move ตรงๆ ผ่าน SQL — ไม่ผ่าน ORM compute
        # เพื่อกัน trigger chain ของ bi_sale_purchase_discount_with_tax
        cr.execute("""
            UPDATE account_move
            SET amount_untaxed = %s,
                amount_tax = %s,
                amount_total = %s
            WHERE id = %s
        """, (target_untaxed, target_tax, target_total, self.id))

        # === 5) SQL sync bi_sale_purchase_discount_with_tax fields ===
        # ตั้ง subtotal_without_discount = target_untaxed → ส่วนลด = 0
        # ถ้า bi recompute ภายหลัง สูตร untaxed = subtotal_wo_disc - discount
        # ก็ให้ผลลัพธ์ = target_untaxed (no drift หลัง reconcile)
        if 'amount_price_subtotal_without_discount' in self._fields:
            cr.execute("""
                UPDATE account_move
                SET amount_price_subtotal_without_discount = %s
                WHERE id = %s
            """, (target_untaxed, self.id))

        if 'discount_amt_line' in self._fields:
            cr.execute("""
                UPDATE account_move
                SET discount_amt_line = 0
                WHERE id = %s
            """, (self.id,))

        if 'amount_price_total_full' in self._fields:
            cr.execute("""
                UPDATE account_move
                SET amount_price_total_full = %s
                WHERE id = %s
            """, (target_total, self.id))

        # === 6) Sync amount_residual บน receivable/payable line ===
        # line.amount_residual เป็น stored compute ที่อ่านจาก line.balance
        # แต่ SQL UPDATE balance ของเราไม่ trigger recompute → ค้างค่าเดิม
        # → "ยอดเงินค้างชำระ" บนฟอร์มเลยไม่ตรงกับ amount_total ที่แก้ไป
        #
        # update เฉพาะ line ที่ยังไม่ partially-reconciled (invoice ใหม่ที่
        # ยังไม่จ่าย) เพื่อกันทับ residual ของ invoice ที่ผ่อนชำระไปบางส่วน
        cr.execute("""
            UPDATE account_move_line aml
            SET amount_residual = aml.balance,
                amount_residual_currency = aml.amount_currency
            FROM account_account aa
            JOIN account_account_type aat ON aat.id = aa.user_type_id
            WHERE aml.account_id = aa.id
              AND aml.move_id = %s
              AND aat.type IN ('receivable', 'payable')
              AND NOT EXISTS (
                  SELECT 1 FROM account_partial_reconcile pr
                  WHERE pr.debit_move_id = aml.id
                     OR pr.credit_move_id = aml.id
              )
        """, (self.id,))

        # === 7) Sync move.amount_residual ===
        # move.amount_residual เป็น stored compute จาก sum(line.amount_residual)
        # ของ receivable/payable lines — ก็ต้อง SQL UPDATE ทับเช่นกัน
        cr.execute("""
            SELECT COALESCE(SUM(aml.amount_residual), 0)
            FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            JOIN account_account_type aat ON aat.id = aa.user_type_id
            WHERE aml.move_id = %s
              AND aat.type IN ('receivable', 'payable')
        """, (self.id,))
        residual_sum = float(cr.fetchone()[0] or 0)
        # แสดงผลใช้ค่าสัมบูรณ์ (ตาม convention ของ Odoo สำหรับ invoice/refund)
        move_amount_residual = abs(currency.round(residual_sum))
        cr.execute("""
            UPDATE account_move
            SET amount_residual = %s
            WHERE id = %s
        """, (move_amount_residual, self.id))

        # === Invalidate ORM cache (ให้ครั้งต่อไปอ่านค่าจาก DB ใหม่) ===
        self.invalidate_cache(
            ['amount_untaxed', 'amount_tax', 'amount_total',
             'amount_residual'],
            [self.id]
        )
        if 'amount_price_subtotal_without_discount' in self._fields:
            self.invalidate_cache(
                ['amount_price_subtotal_without_discount'], [self.id]
            )
        if 'discount_amt_line' in self._fields:
            self.invalidate_cache(['discount_amt_line'], [self.id])
        if 'amount_price_total_full' in self._fields:
            self.invalidate_cache(['amount_price_total_full'], [self.id])

        # ทุก line ของ move นี้ต้อง invalidate residual เพื่อให้ form อ่าน
        # ค่าใหม่ที่เราเพิ่ง SQL UPDATE — ไม่ใช่แค่ line ที่อยู่ใน updates
        self.invalidate_cache(['line_ids'], [self.id])
        self.line_ids.invalidate_cache(
            ['debit', 'credit', 'balance',
             'amount_currency', 'amount_residual',
             'amount_residual_currency'],
        )

        _logger.info(
            'VAT From Total [%s] amounts: '
            'untaxed=%.2f tax=%.2f total=%.2f (counterpart diff=%.2f)',
            self.name or 'Draft',
            target_untaxed, target_tax, target_total, total_diff,
        )

    # =====================================================================
    # Helper: คำนวณ target tax amounts
    # =====================================================================
    def _calc_target_taxes(self):
        """Returns: {tax_id: target_tax_amount} หรือ None"""
        full = self._calc_target_taxes_full()
        if not full:
            return None
        return {tid: v['tax'] for tid, v in full.items()}

    def _calc_target_taxes_full(self):
        """Returns: {tax_id: {'tax': amount, 'untaxed': amount}} หรือ {}"""
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id

        invoice_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )
        if not invoice_lines:
            return {}

        tax_map = {}
        for line in invoice_lines:
            for tax in line.tax_ids:
                if tax.amount_type == 'percent' and tax.id not in tax_map:
                    tax_map[tax.id] = tax

        if not tax_map:
            return {}

        result = {}

        method = self.vat_calculation_method or 'from_total'

        for tax_id, tax in tax_map.items():
            lines_with_tax = invoice_lines.filtered(
                lambda l, t=tax: t in l.tax_ids
            )
            rate = tax.amount

            if tax.price_include:
                if method == 'per_line':
                    # Per-line: ถอด VAT ทีละบรรทัดแล้วรวม
                    group_tax = 0.0
                    group_untaxed = 0.0
                    for l in lines_with_tax:
                        line_incl = self._get_line_effective_amount(
                            l, currency)
                        line_tax = currency.round(
                            line_incl * rate / (100.0 + rate))
                        group_tax += line_tax
                        group_untaxed += (line_incl - line_tax)
                    group_tax = currency.round(group_tax)
                    group_untaxed = currency.round(group_untaxed)
                else:
                    # From-total: ถอด VAT จากยอดรวมครั้งเดียว
                    total_incl = sum(
                        self._get_line_effective_amount(l, currency)
                        for l in lines_with_tax
                    )
                    group_tax = currency.round(
                        total_incl * rate / (100.0 + rate))
                    group_untaxed = total_incl - group_tax
            else:
                if method == 'per_line':
                    # Per-line: คำนวณ tax ทีละบรรทัดแล้วรวม
                    group_tax = 0.0
                    group_untaxed = 0.0
                    for l in lines_with_tax:
                        line_untaxed = self._get_line_effective_amount(
                            l, currency)
                        line_tax = currency.round(
                            line_untaxed * rate / 100.0)
                        group_tax += line_tax
                        group_untaxed += line_untaxed
                    group_tax = currency.round(group_tax)
                    group_untaxed = currency.round(group_untaxed)
                else:
                    # From-total: คำนวณ tax จากยอดรวมครั้งเดียว
                    group_untaxed = sum(
                        self._get_line_effective_amount(l, currency)
                        for l in lines_with_tax
                    )
                    group_tax = currency.round(
                        group_untaxed * rate / 100.0)

            result[tax_id] = {
                'tax': group_tax,
                'untaxed': group_untaxed,
            }

        return result

    # =====================================================================
    # Helper: ยอด line หลังหักส่วนลด (tax-included amount)
    # =====================================================================
    def _get_line_effective_amount(self, line, currency):
        raw = currency.round(abs(line.price_unit) * line.quantity)

        # bi_module discount — ใช้ discount_method/discount_amount โดยตรง
        # เพื่อหลีกเลี่ยงปัญหา timing ของ discount_amt (computed field)
        if hasattr(line, 'discount_method') and hasattr(line, 'discount_amount'):
            if line.discount_method == 'per' and (line.discount_amount or 0.0) > 0:
                # percentage discount: ได้ยอด tax-included หลังหักส่วนลดเสมอ
                return currency.round(
                    raw * (1.0 - line.discount_amount / 100.0)
                )
            elif line.discount_method == 'fix' and (line.discount_amount or 0.0) > 0:
                # fixed discount: discount_amount เป็นยอด untaxed
                # ต้องแปลงเป็น tax-included ก่อนหัก
                tax_rate = sum(
                    t.amount for t in line.tax_ids
                    if t.amount_type == 'percent'
                    and t.price_include and t.amount > 0
                )
                if tax_rate:
                    discount_incl = currency.round(
                        line.discount_amount * (100.0 + tax_rate) / 100.0
                    )
                else:
                    discount_incl = line.discount_amount
                return currency.round(raw - discount_incl)

        # Fallback: bi_module computed discount_amt
        if hasattr(line, 'discount_amt'):
            bi_discount = abs(line.discount_amt or 0.0)
            if bi_discount > 0.0:
                return currency.round(raw - bi_discount)

        # Standard Odoo percentage discount
        if line.discount:
            return currency.round(raw * (1.0 - line.discount / 100.0))

        return raw
