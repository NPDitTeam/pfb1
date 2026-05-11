import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    use_new_calc = fields.Boolean(
        related='move_id.use_new_calc',
        store=True,
        readonly=True,
    )

    use_baan_kheaw = fields.Boolean(
        related='move_id.use_baan_kheaw',
        store=True,
        readonly=True,
    )

    vat_from_total = fields.Boolean(
        related='move_id.vat_from_total',
        store=True,
        readonly=True,
    )

    price_unit_no_vat = fields.Float(
        string='ราคาต่อหน่วย (ถอด VAT)',
        compute='_compute_price_unit_no_vat',
        inverse='_inverse_price_unit_no_vat',
        store=True,
        digits=(16, 2),
    )

    @api.depends('price_unit', 'tax_ids', 'use_new_calc', 'use_baan_kheaw')
    def _compute_price_unit_no_vat(self):
        for line in self:
            move = line.move_id
            use_new_calc = move.use_new_calc if move else False
            use_baan_kheaw = move.use_baan_kheaw if move else False
            has_vat_7_incl = bool(line.tax_ids) and any(
                t.price_include and abs(t.amount - 7.0) < 0.01
                for t in line.tax_ids
            )
            if use_new_calc and has_vat_7_incl and not use_baan_kheaw:
                line.price_unit_no_vat = round(line.price_unit / 1.07, 2)
            else:
                line.price_unit_no_vat = line.price_unit

    def _inverse_price_unit_no_vat(self):
        """User แก้ค่าในฟิลด์ ex-VAT → กลับไปอัพเดต price_unit (incl-VAT)"""
        for line in self:
            move = line.move_id
            use_new_calc = move.use_new_calc if move else False
            use_baan_kheaw = move.use_baan_kheaw if move else False
            has_vat_7_incl = bool(line.tax_ids) and any(
                t.price_include and abs(t.amount - 7.0) < 0.01
                for t in line.tax_ids
            )
            if use_new_calc and has_vat_7_incl and not use_baan_kheaw:
                line.price_unit = round(line.price_unit_no_vat * 1.07, 2)
            else:
                line.price_unit = line.price_unit_no_vat

    @api.onchange('price_unit_no_vat')
    def _onchange_price_unit_no_vat(self):
        # ในฟอร์ม onchange การ set ผ่าน inverse ไม่ trigger _onchange_price_subtotal
        # → sync price_unit เอง แล้วเรียก recomputation chain ของ Odoo
        # หลังอัพเดท invoice line ต้องเรียก move._recompute_dynamic_lines
        # เพื่อ sync tax line + receivable/payable ให้ debit = credit
        # ไม่งั้น save แล้วจะ "Cannot create unbalanced journal entry"
        moves_to_recompute = self.env['account.move']
        for line in self:
            move = line.move_id
            use_new_calc = move.use_new_calc if move else False
            use_baan_kheaw = move.use_baan_kheaw if move else False
            has_vat_7_incl = bool(line.tax_ids) and any(
                t.price_include and abs(t.amount - 7.0) < 0.01
                for t in line.tax_ids
            )
            if use_new_calc and has_vat_7_incl and not use_baan_kheaw:
                new_price_unit = round(line.price_unit_no_vat * 1.07, 2)
            else:
                new_price_unit = line.price_unit_no_vat
            if line.price_unit != new_price_unit:
                line.price_unit = new_price_unit
            if not move.is_invoice(include_receipts=True):
                continue
            line.update(line._get_price_total_and_subtotal())
            line.update(line._get_fields_onchange_subtotal())
            moves_to_recompute |= move
        for move in moves_to_recompute:
            # ต้องใช้ recompute_all_taxes=True เพราะ amount ของ tax line
            # ต้องคำนวณใหม่ทั้งหมด (ไม่ใช่แค่ tax_base_amount)
            # ไม่งั้น tax debit/credit ค้างค่าเดิม → unbalanced
            move._recompute_dynamic_lines(
                recompute_all_taxes=True,
                recompute_tax_base_amount=True,
            )

    def _npd_compute_method_a(self):
        """Method A: subtotal = round(price_unit / 1.07, 2) × qty

        ใช้กับ invoice line ที่ใช้สูตรปกติ price_unit × qty / 1.07 เท่านั้น
        ข้าม line ที่ถูกสร้างด้วย debit/credit ตรงๆ (เช่น advance_clear,
        bank statement, manual journal entry) ซึ่งไม่มี price_unit
        ข้าม move ที่ติ๊ก use_baan_kheaw (ใช้ราคาบ้านเขียวตรงๆ — สูตร Odoo default)
        """
        result = {}
        for line in self:
            # Guard: เฉพาะใบกำกับ/ใบเสร็จเท่านั้น
            # (entry/payment/อื่นๆ ที่ set debit/credit ตรงไม่ผ่าน price_unit จะข้าม
            # ไม่งั้น price_unit=0 จะทำให้ method A เซ็ต debit=0 ทับของจริง)
            if not line.move_id.is_invoice(include_receipts=True):
                continue
            if not line.use_new_calc:
                continue
            if line.use_baan_kheaw:
                continue
            if not line.price_unit or not line.quantity or not line.tax_ids:
                continue
            has_vat_7_incl = any(
                t.price_include and abs(t.amount - 7.0) < 0.01
                for t in line.tax_ids
            )
            if not has_vat_7_incl:
                continue
            unit_ex_vat = round(line.price_unit / 1.07, 2)
            new_subtotal = round(unit_ex_vat * line.quantity, 2)
            new_tax = round(new_subtotal * 0.07, 2)
            new_price_total = round(new_subtotal + new_tax, 2)
            result[line.id] = (new_subtotal, new_price_total, new_tax)
        return result

    def _npd_write_subtotal_sql(self, line, new_subtotal, new_total, new_tax=None):
        """เขียน price_subtotal/total + debit/credit/balance ลง DB ผ่าน SQL
        ใช้ร่วมกันระหว่าง Method A และ baan_kheaw reset

        new_tax: ไม่ได้ใช้ใน SQL UPDATE (price_tax เป็น non-stored compute
                 field ของ Odoo 14 ไม่มี column ใน DB) — เก็บ parameter ไว้
                 เผื่อ caller ต้องส่ง intent ของค่า tax ให้ helper logic อื่น
                 ภายหลัง. ผลรวม tax ที่ใช้ใน rebalance อ่านจาก
                 price_total - price_subtotal (หรือ price_tax field
                 ของ ORM ที่ recompute จากสองตัวนี้)
        """
        cr = self.env.cr
        sign = 1 if line.move_id.move_type in line.move_id.get_outbound_types() else -1
        new_amount_currency = round(new_subtotal * sign, 2)
        balance = line.currency_id._convert(
            new_amount_currency,
            line.company_id.currency_id,
            line.company_id,
            line.date or fields.Date.context_today(line),
        )
        new_debit = round(balance, 2) if balance > 0 else 0.0
        new_credit = round(-balance, 2) if balance < 0 else 0.0
        cr.execute(
            """
            UPDATE account_move_line
            SET price_subtotal = %s,
                price_total = %s,
                amount_currency = %s,
                debit = %s,
                credit = %s,
                balance = %s
            WHERE id = %s
            """,
            (new_subtotal, new_total, new_amount_currency,
             new_debit, new_credit, round(balance, 2), line.id),
        )
        if 'price_subtotal_without_discount' in line._fields:
            cr.execute(
                "UPDATE account_move_line SET price_subtotal_without_discount = %s WHERE id = %s",
                (new_subtotal, line.id),
            )
        if 'lost_item_amount' in line._fields:
            cr.execute(
                "UPDATE account_move_line SET lost_item_amount = %s WHERE id = %s",
                (new_subtotal, line.id),
            )
        if 'price_total_full' in line._fields:
            cr.execute(
                "UPDATE account_move_line SET price_total_full = %s WHERE id = %s",
                (new_total, line.id),
            )

    def _npd_compute_baan_kheaw_reset(self):
        """คำนวณ price_subtotal/total ผ่านสูตร Odoo default สำหรับ line ที่ติ๊ก
        use_baan_kheaw (Method A skip ตอน toggle เพิ่งเปลี่ยนมา ค่าใน DB ค้าง
        ค่าเก่าของ Method A) — return dict line_id -> (subtotal, total)"""
        result = {}
        for line in self:
            if not line.move_id.is_invoice(include_receipts=True):
                continue
            if not line.use_new_calc or not line.use_baan_kheaw:
                continue
            if not line.price_unit or not line.quantity or not line.tax_ids:
                continue
            has_vat_7_incl = any(
                t.price_include and abs(t.amount - 7.0) < 0.01
                for t in line.tax_ids
            )
            if not has_vat_7_incl:
                continue
            sub_vals = line._get_price_total_and_subtotal()
            new_subtotal = sub_vals.get('price_subtotal', line.price_subtotal)
            new_total = sub_vals.get('price_total', line.price_total)
            # idempotent: skip if already at Odoo default
            if (abs(line.price_subtotal - new_subtotal) < 0.001 and
                    abs(line.price_total - new_total) < 0.001):
                continue
            result[line.id] = (new_subtotal, new_total)
        return result

    def _npd_force_round_sql(self):
        # === Flush pending ORM writes ก่อน SQL reads ===
        # บังคับให้ ORM เขียน target_amount_total / line.balance ฯลฯ ที่อาจ
        # buffer อยู่ใน cache ลง DB ก่อนที่ SQL queries ของเราจะอ่าน
        # ไม่งั้นจะเจอ "ครั้งแรกไม่ทำงาน ครั้งที่สองถึงทำงาน" เพราะ
        # cache ยังไม่ flush ตอน first call
        self.env['account.move'].flush([
            'target_amount_total', 'amount_total', 'amount_tax',
            'amount_untaxed', 'amount_residual',
        ])
        self.env['account.move.line'].flush([
            'price_subtotal', 'price_total', 'debit', 'credit',
            'balance', 'amount_currency', 'amount_residual',
        ])

        rounded = self._npd_compute_method_a()
        baan_kheaw_resets = self._npd_compute_baan_kheaw_reset()
        cr = self.env.cr

        # === target_amount_total — บังคับยอดรวมเป๊ะ ===
        # อ่านค่าจาก DB ตรงๆ (ผ่าน SQL) เพื่อกัน ORM cache mismatch
        # — เคยเจอกรณี super().write() อัพเดต cache แต่ value ที่ filter
        # ผ่าน lambda อ่านได้เป็น 0 ทำให้ has_target = False ทั้งที่ user
        # เพิ่งกำหนด target ไว้
        target_value_by_move = {}  # {move_id: target_amount_total}
        moves_with_vat_from_total_ids = set()
        if self:
            all_move_ids = list(set(self.mapped('move_id').ids))
            if all_move_ids:
                cr.execute("""
                    SELECT id, COALESCE(target_amount_total, 0)
                    FROM account_move
                    WHERE id IN %s
                      AND target_amount_total IS NOT NULL
                      AND target_amount_total > 0
                      AND move_type IN ('out_invoice', 'in_invoice',
                          'out_refund', 'in_refund',
                          'out_receipt', 'in_receipt')
                """, (tuple(all_move_ids),))
                for row in cr.fetchall():
                    target_value_by_move[row[0]] = float(row[1])
                # Method B (vat_from_total) — ถ้าติ๊ก ต้อง override move totals
                # + tax line แม้ Method A/baan_kheaw จะไม่ active ก็ตาม
                cr.execute("""
                    SELECT id FROM account_move
                    WHERE id IN %s
                      AND vat_from_total = TRUE
                      AND move_type IN ('out_invoice', 'in_invoice',
                          'out_refund', 'in_refund',
                          'out_receipt', 'in_receipt')
                """, (tuple(all_move_ids),))
                moves_with_vat_from_total_ids = set(
                    row[0] for row in cr.fetchall())
        moves_with_target_ids = set(target_value_by_move.keys())

        if (not rounded and not baan_kheaw_resets
                and not moves_with_target_ids
                and not moves_with_vat_from_total_ids):
            return

        moves_changed = set()
        for line in self:
            if line.id in rounded:
                new_subtotal, new_total, new_tax = rounded[line.id]
                self._npd_write_subtotal_sql(
                    line, new_subtotal, new_total, new_tax)
                moves_changed.add(line.move_id.id)
            elif line.id in baan_kheaw_resets:
                new_subtotal, new_total = baan_kheaw_resets[line.id]
                # baan_kheaw reset: ปล่อยให้ helper คำนวณ tax = total - subtotal
                self._npd_write_subtotal_sql(line, new_subtotal, new_total)
                moves_changed.add(line.move_id.id)

        # บังคับให้ moves ที่มี target ถูกประมวลผลใน loop ด้านล่าง
        # แม้จะไม่มี line update ก็ตาม (เพื่อให้ tax line + receivable +
        # move totals ถูก override ตาม target)
        moves_changed |= moves_with_target_ids
        # บังคับให้ moves ที่ติ๊ก vat_from_total เข้า loop ด้วย
        # เพื่อ override tax line + move totals = Method B
        moves_changed |= moves_with_vat_from_total_ids

        for move_id in moves_changed:
            move = self.env['account.move'].browse(move_id)
            move_sign = 1 if move.move_type in move.get_outbound_types() else -1

            # Rebalance tax lines: amount = SUM(price_total - price_subtotal)
            # ใช้ผลรวมของภาษีที่ Method A ปัดเศษไว้ราย line แล้ว
            # (= วิธีคำนวณเดียวกับ SO — ตรงกันระหว่าง SO/Invoice ไม่ drift 0.01)
            #
            # หมายเหตุ: account.move.line ของ Odoo 14 ไม่มี column price_tax
            # (เป็น non-stored compute) ใช้ price_total - price_subtotal
            # ซึ่ง Method A เขียนทั้งคู่ผ่าน SQL ไว้แล้ว → ค่าเท่ากับ
            # SUM(per-line tax round)
            #
            # เดิมใช้ formula round(SUM(price_subtotal) × rate, 2) ซึ่งให้ค่า
            # ต่างกับ SO 0.01 บาทในบางเคส เช่น:
            #   round(2907.20 × 0.07, 2) = round(203.504, 2) = 203.50
            #   แต่ SO รวมราย line: 58.86 + 125.61 + 19.04 = 203.51
            #
            # === target_amount_total override (v17) ===
            # ถ้า move.target_amount_total > 0 → User ต้องการ hit ยอดเป๊ะ
            # → ปรับ tax line = target - subtotal (override formula ปกติ)
            # อ่าน target จาก DB-cached dict (ไม่ใช่ ORM record cache) เพื่อกัน
            # cache mismatch — guarantee ว่าค่าตรงกับ DB จริงๆ
            target_value = target_value_by_move.get(move_id, 0.0)
            has_target = target_value > 0
            # Method B flag — ถ้า move นี้ติ๊ก vat_from_total
            use_method_b = move_id in moves_with_vat_from_total_ids
            if move.is_invoice(include_receipts=True):
                for tax_line in move.line_ids.filtered(lambda l: l.tax_line_id):
                    tax_obj = tax_line.tax_line_id
                    cr.execute(
                        """
                        SELECT COALESCE(SUM(aml.price_subtotal), 0),
                               COALESCE(SUM(aml.price_total), 0)
                        FROM account_move_line aml
                        JOIN account_move_line_account_tax_rel rel
                          ON rel.account_move_line_id = aml.id
                        WHERE rel.account_tax_id = %s
                          AND aml.move_id = %s
                          AND COALESCE(aml.exclude_from_invoice_tab, FALSE) = FALSE
                        """,
                        (tax_obj.id, move_id),
                    )
                    row = cr.fetchone()
                    base_subtotal = round(float(row[0] or 0), 2)
                    base_total = round(float(row[1] or 0), 2)
                    if has_target:
                        # User กำหนดยอดเป้าหมาย → tax = target - subtotal
                        new_tax_amount = round(
                            target_value - base_subtotal, 2)
                    elif use_method_b and abs(tax_obj.amount - 7.0) < 0.01:
                        # Method B: VAT 7% คิดจากยอดรวม ปัดครั้งเดียว
                        # (ใช้เฉพาะภาษี 7% — ภาษีอื่น เช่น WHT ใช้สูตรเดิม)
                        new_tax_amount = round(
                            base_subtotal * tax_obj.amount / 100.0, 2)
                    else:
                        # Default: tax = SUM(price_total) - SUM(price_subtotal)
                        new_tax_amount = round(base_total - base_subtotal, 2)
                        # Fallback: ถ้า price_total ยังไม่ถูก compute (= 0) ใช้
                        # formula เดิม round(subtotal × rate)
                        if new_tax_amount == 0.0 and base_subtotal:
                            new_tax_amount = round(
                                base_subtotal * tax_obj.amount / 100.0, 2)
                    new_tax_ac = round(new_tax_amount * move_sign, 2)
                    tl_balance = tax_line.currency_id._convert(
                        new_tax_ac,
                        tax_line.company_id.currency_id,
                        tax_line.company_id,
                        tax_line.date or fields.Date.context_today(tax_line),
                    )
                    tl_debit = round(tl_balance, 2) if tl_balance > 0 else 0.0
                    tl_credit = round(-tl_balance, 2) if tl_balance < 0 else 0.0
                    cr.execute(
                        """
                        UPDATE account_move_line
                        SET amount_currency = %s,
                            debit = %s,
                            credit = %s,
                            balance = %s,
                            tax_base_amount = %s
                        WHERE id = %s
                        """,
                        (new_tax_ac, tl_debit, tl_credit,
                         round(tl_balance, 2), base_subtotal, tax_line.id),
                    )
                    # Sync account.move.tax.invoice (l10n_th_tax_invoice)
                    # ค้นหา record ที่ link กับ tax_line นี้แล้วอัพเดทยอดให้ตรง
                    cr.execute(
                        """
                        SELECT to_regclass('account_move_tax_invoice')
                        """
                    )
                    has_tax_invoice_table = cr.fetchone()[0] is not None
                    if has_tax_invoice_table:
                        ti_balance = round(new_tax_amount, 2)
                        cr.execute(
                            """
                            UPDATE account_move_tax_invoice
                            SET tax_base_amount = %s,
                                balance = %s
                            WHERE move_line_id = %s
                            """,
                            (base_subtotal, ti_balance, tax_line.id),
                        )

                # Rebalance receivable/payable lines so debit = credit on the move
                cr.execute(
                    """
                    SELECT COALESCE(SUM(aml.debit - aml.credit), 0),
                           COALESCE(SUM(aml.amount_currency), 0)
                    FROM account_move_line aml
                    JOIN account_account aa ON aa.id = aml.account_id
                    JOIN account_account_type aat ON aat.id = aa.user_type_id
                    WHERE aml.move_id = %s
                      AND aat.type NOT IN ('receivable', 'payable')
                    """,
                    (move_id,),
                )
                row = cr.fetchone()
                sum_other_balance = round(float(row[0] or 0), 2)
                sum_other_ac = round(float(row[1] or 0), 2)

                cr.execute(
                    """
                    SELECT aml.id, aml.debit, aml.credit, aml.amount_currency
                    FROM account_move_line aml
                    JOIN account_account aa ON aa.id = aml.account_id
                    JOIN account_account_type aat ON aat.id = aa.user_type_id
                    WHERE aml.move_id = %s
                      AND aat.type IN ('receivable', 'payable')
                    ORDER BY aml.id
                    """,
                    (move_id,),
                )
                rec_rows = cr.fetchall()
                if rec_rows:
                    target_balance = -sum_other_balance
                    target_ac = -sum_other_ac
                    if len(rec_rows) == 1:
                        rec_id = rec_rows[0][0]
                        rec_debit = round(target_balance, 2) if target_balance > 0 else 0.0
                        rec_credit = round(-target_balance, 2) if target_balance < 0 else 0.0
                        cr.execute(
                            """
                            UPDATE account_move_line
                            SET amount_currency = %s,
                                debit = %s,
                                credit = %s,
                                balance = %s
                            WHERE id = %s
                            """,
                            (target_ac, rec_debit, rec_credit,
                             round(target_balance, 2), rec_id),
                        )
                    else:
                        # ผ่อนชำระหลายงวด — รับ delta เฉพาะบรรทัดแรก เพื่อรักษาสัดส่วนการแบ่งงวด
                        cur_total_balance = round(
                            sum(r[1] - r[2] for r in rec_rows), 2)
                        cur_total_ac = round(sum(r[3] for r in rec_rows), 2)
                        delta_balance = round(target_balance - cur_total_balance, 2)
                        delta_ac = round(target_ac - cur_total_ac, 2)
                        if delta_balance != 0 or delta_ac != 0:
                            first_id, first_debit, first_credit, first_ac = rec_rows[0]
                            new_first_balance = round(
                                first_debit - first_credit + delta_balance, 2)
                            new_first_ac = round(first_ac + delta_ac, 2)
                            rec_debit = new_first_balance if new_first_balance > 0 else 0.0
                            rec_credit = -new_first_balance if new_first_balance < 0 else 0.0
                            cr.execute(
                                """
                                UPDATE account_move_line
                                SET amount_currency = %s,
                                    debit = %s,
                                    credit = %s,
                                    balance = %s
                                WHERE id = %s
                                """,
                                (new_first_ac, rec_debit, rec_credit,
                                 new_first_balance, first_id),
                            )

            # Move-level totals: ใช้ผลรวม price_subtotal/price_total ราย line
            # tax = SUM(price_total) - SUM(price_subtotal)
            # = ผลรวมของ tax ราย line ที่ Method A ปัดเศษไว้ → ตรงกับ SO
            cr.execute(
                """
                SELECT COALESCE(SUM(price_subtotal), 0),
                       COALESCE(SUM(price_total), 0)
                FROM account_move_line
                WHERE move_id = %s
                AND (exclude_from_invoice_tab = FALSE OR exclude_from_invoice_tab IS NULL)
                """,
                (move_id,),
            )
            row = cr.fetchone()
            untaxed = round(float(row[0] or 0), 2)
            total_with_tax = round(float(row[1] or 0), 2)

            # === target_amount_total override (v17) ===
            if has_target:
                # User บังคับยอดรวม → คำนวณ tax ย้อนกลับจาก target - subtotal
                total = round(target_value, 2)
                tax = round(total - untaxed, 2)
            elif use_method_b:
                # Method B: VAT 7% คิดจาก subtotal ของบรรทัดที่มี 7% VAT inclusive
                # เท่านั้น (ไม่ใช่ทั้ง untaxed) — บรรทัดที่ไม่มี VAT เช่น
                # เงินประกัน ค่าขนส่งไม่มี VAT → ไม่บวก 7%
                # บรรทัดที่มีภาษีอื่น (WHT) → ใช้สูตรเดิม per-line
                cr.execute(
                    """
                    SELECT COALESCE(SUM(aml.price_subtotal), 0),
                           COALESCE(SUM(aml.price_total - aml.price_subtotal), 0)
                    FROM account_move_line aml
                    JOIN account_move_line_account_tax_rel rel
                      ON rel.account_move_line_id = aml.id
                    JOIN account_tax tax ON tax.id = rel.account_tax_id
                    WHERE aml.move_id = %s
                      AND COALESCE(aml.exclude_from_invoice_tab, FALSE) = FALSE
                      AND tax.price_include = TRUE
                      AND ABS(tax.amount - 7.0) < 0.01
                    """,
                    (move_id,),
                )
                row_b = cr.fetchone()
                taxable_7_subtotal = round(float(row_b[0] or 0), 2)
                per_line_tax_7 = round(float(row_b[1] or 0), 2)
                per_line_tax_all = round(total_with_tax - untaxed, 2)
                if taxable_7_subtotal > 0:
                    # มีบรรทัด VAT 7% → Method B สำหรับส่วน 7%
                    method_b_vat = round(taxable_7_subtotal * 0.07, 2)
                    # ภาษีอื่น (WHT ฯลฯ) = ผลรวม per-line tax ลบส่วนของ 7%
                    other_taxes = round(per_line_tax_all - per_line_tax_7, 2)
                    tax = round(method_b_vat + other_taxes, 2)
                else:
                    # ไม่มีบรรทัด VAT 7% (เช่น ใบเงินประกัน) → ใช้ผลรวม per-line
                    # ไม่ apply 7% fallback เพราะใบนี้ไม่ควรมี VAT
                    tax = per_line_tax_all
                total = round(untaxed + tax, 2)
            else:
                tax = round(total_with_tax - untaxed, 2)
                # Fallback: ถ้า price_total ยังไม่ compute (= 0) ใช้ formula เดิม
                if tax == 0.0 and untaxed:
                    tax = round(untaxed * 0.07, 2)
                total = round(untaxed + tax, 2)
            cr.execute(
                """
                UPDATE account_move
                SET amount_untaxed = %s,
                    amount_tax = %s,
                    amount_total = %s
                WHERE id = %s
                """,
                (untaxed, tax, total, move_id),
            )
            if 'amount_price_subtotal_without_discount' in move._fields:
                cr.execute(
                    "UPDATE account_move SET amount_price_subtotal_without_discount = %s WHERE id = %s",
                    (untaxed, move_id),
                )
            if 'amount_price_total_full' in move._fields:
                cr.execute(
                    "UPDATE account_move SET amount_price_total_full = %s WHERE id = %s",
                    (total, move_id),
                )
            if 'discount_amt_line' in move._fields:
                cr.execute(
                    "UPDATE account_move SET discount_amt_line = 0 WHERE id = %s",
                    (move_id,),
                )

            # === Sync amount_residual ของ receivable line + move ===
            # หลัง update line.balance ของ receivable, line.amount_residual
            # ไม่ recompute เอง (stored compute, ไม่ใช่ trigger จาก SQL)
            # → SQL UPDATE = balance สำหรับ unreconciled lines
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
            """, (move_id,))
            # move.amount_residual = abs(sum receivable line residuals)
            cr.execute("""
                SELECT COALESCE(SUM(aml.amount_residual), 0)
                FROM account_move_line aml
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN account_account_type aat ON aat.id = aa.user_type_id
                WHERE aml.move_id = %s
                  AND aat.type IN ('receivable', 'payable')
            """, (move_id,))
            residual_sum = float(cr.fetchone()[0] or 0)
            cr.execute("""
                UPDATE account_move SET amount_residual = %s WHERE id = %s
            """, (abs(round(residual_sum, 2)), move_id))

        self.env.cache.invalidate()

    def _compute_amount(self):
        res = super()._compute_amount()
        rounded = self._npd_compute_method_a()
        for line in self:
            if line.id in rounded:
                new_subtotal, new_total, new_tax = rounded[line.id]
                line.price_subtotal = new_subtotal
                line.price_total = new_total
                if 'price_subtotal_without_discount' in line._fields:
                    line.price_subtotal_without_discount = new_subtotal
        return res


class AccountMove(models.Model):
    _inherit = 'account.move'

    use_new_calc = fields.Boolean(
        string='คิดราคาต่อหน่วยแบบถอด Vat',
        default=True,
        copy=True,
        tracking=True,
        help='True = ใช้สูตรใหม่: ราคาต่อหน่วย ถอด VAT 2 ทศนิยม + คำนวณรวมจากราคานั้น × qty (Method A). '
             'False = ใช้สูตรระบบเดิม.',
    )

    use_baan_kheaw = fields.Boolean(
        string='ใช้ราคาจากบ้านเขียว',
        default=False,
        copy=True,
        tracking=True,
        help='ติ๊ก = ไม่ใช้ฟังก์ชันคำนวณใหม่ (Method A) เลย และอัพเดทยอด '
             'ด้วยระบบเดิมของ Odoo. ค่านี้ส่งต่อจาก sale.order อัตโนมัติ',
    )

    vat_from_total = fields.Boolean(
        string='คำนวณ VAT จากยอดรวม',
        default=True,
        copy=True,
        tracking=True,
        help='True (Method B) = amount_tax = round(amount_untaxed × 0.07, 2) '
             'ปัดครั้งเดียวระดับ move + sync tax line + receivable. '
             'False = sum ของ tax รายบรรทัด (สูตรเดิม). '
             'ค่านี้ส่งต่อจาก sale.order อัตโนมัติ',
    )

    target_amount_total = fields.Monetary(
        string='ยอดเป้าหมาย (Target Total)',
        currency_field='currency_id',
        default=0.0,
        copy=False,
        tracking=True,
        help='กรอกยอด incl-VAT ที่ต้องการให้ใบนี้สรุปเป๊ะ — ระบบจะปรับ '
             'tax line + receivable + amount_total ให้ตรง target อัตโนมัติ '
             '(ใช้สำหรับใบลดหนี้ที่ต้อง hit ยอดเป๊ะตามเงื่อนไขภายใน). '
             'ปล่อยเป็น 0 = ไม่ override ใช้สูตร Method A ปกติ. '
             'หลังกรอกแล้วกด Save → ยอดจะอัพเดทอัตโนมัติ',
    )

    can_edit_use_new_calc = fields.Boolean(
        compute='_compute_can_edit_use_new_calc',
    )

    @api.depends_context('uid')
    def _compute_can_edit_use_new_calc(self):
        has_perm = self.env.user.can_edit_use_new_calc
        for rec in self:
            rec.can_edit_use_new_calc = has_perm

    @api.onchange('use_new_calc', 'use_baan_kheaw', 'vat_from_total')
    def _onchange_npd_calc_flags(self):
        """รีเฟรช price_unit_no_vat ของทุก invoice line ทันทีใน UI
        invalidate cache แล้วเรียก compute ตรงๆ
        (vat_from_total ไม่กระทบราคา/หน่วย แต่ trigger recompute เพื่อ
        ความสอดคล้องของ form)"""
        if not self.invoice_line_ids:
            return
        self.invoice_line_ids.invalidate_cache(['price_unit_no_vat'])
        self.invoice_line_ids._compute_price_unit_no_vat()

    @api.model_create_multi
    def create(self, vals_list):
        # บังคับ use_baan_kheaw=True ใน Debit Note (debit_origin_id ถูกตั้งโดย wizard)
        # — Debit Note ต้องใช้ราคาจากบ้านเขียวเท่านั้น (ไม่ใช้ Method A)
        for vals in vals_list:
            if vals.get('debit_origin_id'):
                vals['use_baan_kheaw'] = True
        # ปิด _check_balanced ของ Odoo ระหว่าง super().create() เพราะ
        # Method A จะปรับ subtotal/tax/receivable หลังจากนั้น — ถ้าเช็คตอนนี้
        # อาจ fail บน intermediate state สำหรับ credit note (out_refund)
        moves = super(AccountMove, self.with_context(check_move_validity=False)).create(vals_list)
        # Auto-untick vat_from_total สำหรับใบที่ไม่มี VAT 7% inclusive ใน line
        # — เคสที่เจอ: SO เช่ารถ (VAT 7%) → กดปุ่ม "รับเงินประกัน" → สร้างใบเงิน
        # ประกัน (ไม่มี VAT) แต่ flag สืบมาจาก SO → ใบเงินประกันถูกติ๊ก vat_from_total
        # → Method B บวก 7% เกินมา → ยอดไม่ตรง
        # แก้: เช็คทันทีหลังสร้าง ถ้าไม่มี line ใดมี 7% VAT inclusive → ตั้ง False
        moves_to_untick_ids = []
        for move in moves:
            if (move.vat_from_total
                    and move.is_invoice(include_receipts=True)
                    and move.invoice_line_ids):
                has_7_vat = any(
                    any(t.price_include and abs(t.amount - 7.0) < 0.01
                        for t in line.tax_ids)
                    for line in move.invoice_line_ids
                )
                if not has_7_vat:
                    moves_to_untick_ids.append(move.id)
        if moves_to_untick_ids:
            # SQL ตรงๆ เพื่อไม่ trigger write override + round logic ซ้ำ
            cr = self.env.cr
            cr.execute(
                "UPDATE account_move SET vat_from_total = FALSE WHERE id IN %s",
                (tuple(moves_to_untick_ids),),
            )
            cr.execute(
                "UPDATE account_move_line SET vat_from_total = FALSE "
                "WHERE move_id IN %s",
                (tuple(moves_to_untick_ids),),
            )
            untick_moves = self.env['account.move'].browse(moves_to_untick_ids)
            untick_moves.invalidate_cache(['vat_from_total'])
            untick_moves.invoice_line_ids.invalidate_cache(['vat_from_total'])
        moves.invoice_line_ids._npd_force_round_sql()
        if self._context.get('check_move_validity', True):
            # ตรวจสมดุลเฉพาะ moves ที่ posted + มี line (ข้าม draft/cancel/empty)
            # — draft/cancel state ไม่ต้อง balanced ใน Odoo (เคารพ semantics เดิม)
            moves_to_check = moves.filtered(
                lambda m: m.line_ids and m.state == 'posted'
            )
            if moves_to_check:
                moves_to_check._check_balanced()
        return moves

    def write(self, vals):
        if self._context.get('npd_skip_round'):
            return super().write(vals)
        # บังคับ use_baan_kheaw=True สำหรับ Debit Note
        # ถ้า user toggle เป็น False หรือมี debit_origin_id ใน vals → บังคับเป็น True
        debit_moves = self.filtered('debit_origin_id')
        if debit_moves and vals.get('use_baan_kheaw') is False:
            vals = dict(vals, use_baan_kheaw=True)
        elif vals.get('debit_origin_id') and vals.get('use_baan_kheaw') is not True:
            vals = dict(vals, use_baan_kheaw=True)
        # ปิด _check_balanced ของ Odoo ระหว่าง super().write() เพราะ:
        # 1) Odoo's _recompute_tax_lines ลบ tax line เก่า + สร้างใหม่ (Odoo formula)
        # 2) ระหว่าง 2 step นั้น move อาจ unbalanced ชั่วคราว
        # 3) Method A ของเราจะปรับ subtotal + รี-balance tax/receivable หลังจากนั้น
        # การเช็ค balance ก่อนเรา rebalance ทำให้ credit note พังด้วย
        # "Cannot create unbalanced journal entry" (diff = VAT amount)
        res = super(AccountMove, self.with_context(check_move_validity=False)).write(vals)
        self.with_context(npd_skip_round=True).invoice_line_ids._npd_force_round_sql()
        # validate ยอดสุดท้าย เฉพาะ moves ที่ posted + มี line
        # — draft/cancel state ไม่ต้อง balanced (กรณีกดยกเลิกใบรับชำระ
        # state จะเปลี่ยนเป็น cancel ระหว่างทางและบรรทัดอาจถูกแก้/ลบ
        # ถ้าเรา check ตอนนี้จะ block การยกเลิก)
        if self._context.get('check_move_validity', True):
            moves_to_check = self.filtered(
                lambda m: m.line_ids and m.state == 'posted'
            )
            if moves_to_check:
                moves_to_check._check_balanced()
        return res

    def action_post(self):
        # Method A/B + rebalance ก่อน super() เพื่อให้ DB อยู่ในสภาพ balanced
        self.with_context(npd_skip_round=True).invoice_line_ids._npd_force_round_sql()
        # ปิด _check_balanced ของ Odoo ระหว่าง super() เพราะ:
        # 1) Odoo's _post() อาจเรียก _recompute_tax_lines / _recompute_dynamic_lines
        #    → reset tax line กลับเป็นสูตร per-line (Method B โดน revert)
        # 2) หลัง super จบ Method B จะ re-apply เพื่อ rebalance อีกรอบ
        # 3) ถ้าไม่ปิด _check_balanced ระหว่างทาง → จะ fail ที่ intermediate state
        #    ด้วย "unbalanced journal entry" 0.02 บาท
        res = super(AccountMove, self.with_context(check_move_validity=False)).action_post()
        # Re-apply Method A/B หลัง super (กรณี Odoo recompute ระหว่าง post)
        self.with_context(npd_skip_round=True).invoice_line_ids._npd_force_round_sql()
        # ตรวจสมดุลเฉพาะ moves ที่ posted + มี line — ข้าม cancel/draft
        posted_moves = self.filtered(
            lambda m: m.line_ids and m.state == 'posted'
        )
        if posted_moves:
            posted_moves._check_balanced()
        return res

    def action_open_decimal_adjust_wizard(self):
        """เปิด wizard "แก้ไขยอดทศนิยม" สำหรับ invoice/credit note/debit note"""
        self.ensure_one()
        allowed_types = ('out_invoice', 'in_invoice',
                         'out_refund', 'in_refund')
        if self.move_type not in allowed_types:
            from odoo.exceptions import UserError
            raise UserError(
                'ฟังก์ชันนี้ใช้ได้เฉพาะใบแจ้งหนี้, ใบลดหนี้, '
                'หรือ Debit Note เท่านั้น'
            )
        return {
            'type': 'ir.actions.act_window',
            'name': 'แก้ไขยอดทศนิยม',
            'res_model': 'npd.adjust.decimal.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
            },
        }
