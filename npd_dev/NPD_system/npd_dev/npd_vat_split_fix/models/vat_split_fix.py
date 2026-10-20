# -*- coding: utf-8 -*-
u"""แก้ "ยอดก่อน VAT / VAT" ของใบแจ้งหนี้-ใบลดหนี้ ให้เท่ากับ ยอดรวม ÷ 1.07

ทำไมต้องมี
    บางใบฐาน/VAT ไม่ตรงกับยอดรวม เช่น CN-1019260004 ตั้ง "ยอดเป้าหมาย" 2,907.44 ไว้
    แต่บรรทัดรวม VAT ได้ 2,902.44 ระบบจึงดันส่วนต่างทั้งก้อนเข้าบรรทัดภาษี
    (VAT 194.88 แทน 190.21) หรือใบที่ปัดราคาต่อหน่วยก่อนคูณจำนวน ทำให้ฐานต่ำไป

หลักการ (เหมือนที่คำนวณใน iTAX)
    ฐานใหม่ = ปัด(ยอดรวม ÷ 1.07, 2)    VAT ใหม่ = ยอดรวม − ฐานใหม่
    ยอดรวมห้ามเปลี่ยน — บรรทัดลูกหนี้และการตัดชำระจึงไม่กระทบ
    ส่วนต่างของฐานเกลี่ยลงบรรทัดรายได้ตามสัดส่วน (largest remainder)

แก้ครบ 4 ที่ (ตามที่เคยแก้มือ ไม่งั้นบัญชี/รายงานภาษีเพี้ยน)
    1. บรรทัดรายได้   2. บรรทัดภาษี   3. หัวเอกสาร
    4. account_move_tax_invoice (ตัวออกรายงานภาษีขาย/ภ.พ.30)
    และฟิลด์คัสตอมที่เก็บยอดซ้ำ (lost_item_amount, price_subtotal_without_discount ฯลฯ)

ทุกใบเก็บค่าเดิมไว้ใน npd.vat.split.fix.log ย้อนกลับได้
"""
import json
import logging
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CENT = Decimal('0.01')
VAT_RATE = Decimal('7')
DIVISOR = Decimal('1.07')
THAI_OFFSET = timedelta(hours=7)
HEADER_LINE_TOLERANCE = Decimal('0.05')
# แฟล็กของ npd_rent_price_round — ใบที่แก้แล้วต้องปิด ไม่งั้นบันทึกใบครั้งถัดไป
# Method A (ปัดราคาต่อหน่วยก่อนคูณ) / Method B (VAT = ฐาน × 7%) จะคำนวณทับยอดที่แก้
# ปิดแล้ว ระบบคิด VAT = ยอดรวม − ฐาน = ค่าที่เราตั้งไว้พอดี จึงนิ่ง
CALC_FLAG_COLS = ('use_new_calc', 'vat_from_total')

# คอลัมน์ที่โมดูลอื่นเก็บยอดของบรรทัดซ้ำไว้ (มีเฉพาะบางฐาน — เช็คก่อนใช้)
PRODUCT_MIRROR_COLS = ('lost_item_amount', 'price_subtotal_without_discount')
TAX_MIRROR_COLS = ('lost_item_amount', 'price_total_full', 'price_unit_no_vat',
                   'price_subtotal_without_discount')
LINE_BASE_COLS = ('price_unit', 'price_subtotal', 'price_total', 'debit', 'credit',
                  'balance', 'amount_currency', 'tax_base_amount')
MOVE_BASE_COLS = ('amount_untaxed', 'amount_tax', 'amount_untaxed_signed', 'amount_tax_signed')
MOVE_EXTRA_COLS = ('amount_price_subtotal_without_discount', 'wht_amt_net', 'target_base_total')


def _d(value):
    return Decimal(str(value or 0))


def _q(value):
    return _d(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _money(value):
    return '{:,.2f}'.format(float(value or 0))


class NpdVatSplitFix(models.AbstractModel):
    _name = 'npd.vat.split.fix'
    _description = 'ตัวแก้ฐาน/VAT ไม่ตรงยอดรวม'

    # ------------------------------------------------------------------
    # ค้นหาใบที่ฐานไม่เท่ากับ ยอดรวม ÷ 1.07
    # ------------------------------------------------------------------
    @api.model
    def find_candidates(self, date_from=None, date_to=None, names=None,
                        move_types=('out_invoice', 'out_refund'), min_diff=0.01):
        where = ["m.state = 'posted'", 'm.move_type IN %s', 'm.amount_tax <> 0',
                 'abs(m.amount_untaxed - round(m.amount_total / 1.07, 2)) >= %s']
        params = [tuple(move_types), max(float(min_diff or 0.01), 0.01) - 0.0001]
        if date_from:
            where.append('m.date >= %s')
            params.append(date_from)
        if date_to:
            where.append('m.date <= %s')
            params.append(date_to)
        if names:
            where.append('m.name IN %s')
            params.append(tuple(names))
        self.env['account.move'].flush(['state', 'move_type', 'amount_tax', 'amount_untaxed',
                                        'amount_total', 'date', 'name'])
        self.env.cr.execute(
            'SELECT m.id FROM account_move m WHERE %s ORDER BY m.date, m.name' % ' AND '.join(where),
            tuple(params))
        return [r[0] for r in self.env.cr.fetchall()]

    # ------------------------------------------------------------------
    # วิเคราะห์ใบเดียว
    # ------------------------------------------------------------------
    @api.model
    def _columns(self, table):
        key = '_npd_cols_%s' % table
        if not hasattr(self.env.registry, key):
            self.env.cr.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,))
            setattr(self.env.registry, key, {r[0] for r in self.env.cr.fetchall()})
        return getattr(self.env.registry, key)

    @api.model
    def _product_lines(self, move):
        return move.line_ids.filtered(
            lambda l: not l.exclude_from_invoice_tab and not l.display_type)

    @api.model
    def _blocking_reason(self, move):
        if move.state != 'posted':
            return u'ยังไม่ลงบันทึก'
        if move.move_type not in ('out_invoice', 'out_refund'):
            return u'ไม่ใช่ใบแจ้งหนี้/ใบลดหนี้ลูกค้า'
        if move.currency_id != move.company_id.currency_id:
            return u'สกุลเงิน %s ไม่ใช่สกุลเงินบริษัท' % (move.currency_id.name or '?')
        product_lines = self._product_lines(move)
        tax_lines = move.line_ids.filtered('tax_line_id')
        if not product_lines:
            return u'ไม่มีบรรทัดสินค้า'
        if len(tax_lines) != 1:
            return u'มีบรรทัดภาษี %d บรรทัด (รองรับเฉพาะ VAT 7%% บรรทัดเดียว)' % len(tax_lines)
        tax = tax_lines.tax_line_id
        if abs(_d(tax.amount) - VAT_RATE) > Decimal('0.01') or tax.amount_type != 'percent':
            return u'ภาษี %s ไม่ใช่ VAT 7%%' % (tax.name or '')
        if not tax.price_include:
            return u'ภาษีแบบแยกนอกราคา (แก้ฐานแล้วยอดรวมจะเปลี่ยน)'
        for line in product_lines:
            if line.tax_ids != tax:
                return u'บรรทัด "%s" ใช้ภาษีต่างจากบรรทัดอื่น' % (line.name or '')[:40]
        if 'wht_amt' in move._fields and _q(move.wht_amt):
            return u'มีหัก ณ ที่จ่าย %s (แก้ฐานแล้วยอดหักจะเปลี่ยน)' % _money(move.wht_amt)
        if self.env['account.move'].sudo().search_count([('tax_cash_basis_move_id', '=', move.id)]):
            return u'มีรายการภาษีเกณฑ์เงินสดผูกอยู่'
        # ส่วนลดรายบรรทัด: npd_rent_price_round คำนวณบรรทัดพวกนี้ใหม่ทุกครั้งที่บันทึก
        # (ไม่ขึ้นกับแฟล็กใด) ยอดที่แก้จะถูกเขียนทับ จึงไม่แตะ
        if 'discount_method' in product_lines._fields and 'discount_amount' in product_lines._fields:
            if product_lines.filtered(lambda l: l.discount_method in ('per', 'fix') and (l.discount_amount or 0) > 0):
                return u'มีส่วนลดรายบรรทัด (ระบบคำนวณบรรทัดส่วนลดใหม่ทุกครั้งที่บันทึก)'
        if 'target_amount_total' in move._fields and (move.target_amount_total or 0) > 0 \
                and abs(_q(move.target_amount_total) - _q(move.amount_total)) >= CENT / 2:
            return u'ยอดเป้าหมาย (%s) ไม่เท่ายอดรวม (%s)' % (_money(move.target_amount_total),
                                                         _money(move.amount_total))
        old_base = sum((_q(l.price_subtotal) for l in product_lines), Decimal('0'))
        if old_base == 0:
            return u'ยอดก่อน VAT เป็น 0'
        # หัวเอกสารต่างจากผลรวมบรรทัดเศษสตางค์ได้ (ใบที่คิด VAT จากยอดรวม) — ถ้าต่างมากกว่านั้น
        # แปลว่าเอกสารผิดปกติจากเรื่องอื่น ให้คนตรวจก่อน
        if abs(_q(move.amount_untaxed) - old_base) > HEADER_LINE_TOLERANCE:
            return u'ยอดก่อน VAT หัวเอกสาร (%s) ต่างจากผลรวมบรรทัด (%s) เกิน %s บาท' % (
                _money(move.amount_untaxed), _money(old_base), _money(HEADER_LINE_TOLERANCE))
        if _q(move.amount_untaxed) + _q(move.amount_tax) != _q(move.amount_total):
            return u'ฐาน + VAT ไม่เท่ายอดรวม (เอกสารผิดปกติ)'
        return None

    @api.model
    def _allocate(self, weights, target):
        u"""แบ่ง target (Decimal) ตามสัดส่วน weights ให้ผลรวมเท่า target เป๊ะ (largest remainder)"""
        total_weight = sum(weights, Decimal('0'))
        if not total_weight:
            return [Decimal('0')] * len(weights)
        raws = [w * target / total_weight for w in weights]
        values = [r.quantize(CENT, rounding=ROUND_DOWN) for r in raws]
        cents = int(((target - sum(values, Decimal('0'))) / CENT).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        order = sorted(range(len(raws)), key=lambda i: (abs(raws[i] - values[i]), abs(weights[i]), -i),
                       reverse=True)
        step = CENT if cents >= 0 else -CENT
        for n in range(abs(cents)):
            values[order[n % len(order)]] += step
        return values

    @api.model
    def analyze(self, move):
        u"""คืน (plan, reason) — reason มีค่า = ใบนี้ข้าม"""
        move = move.sudo()
        reason = self._blocking_reason(move)
        if reason:
            return None, reason
        product_lines = self._product_lines(move)
        tax_line = move.line_ids.filtered('tax_line_id')
        total = _q(move.amount_total)
        old_base = sum((_q(l.price_subtotal) for l in product_lines), Decimal('0'))
        old_tax = _q(move.amount_tax)
        new_base = _q(total / DIVISOR)
        new_tax = total - new_base
        weights = [_q(l.price_subtotal) for l in product_lines]
        new_subs = self._allocate(weights, new_base)
        new_totals = self._allocate([s * DIVISOR for s in new_subs], total)
        return {
            'move_id': move.id,
            'total': total, 'old_base': old_base, 'old_tax': old_tax,
            'new_base': new_base, 'new_tax': new_tax,
            'tax_line_id': tax_line.id,
            'lines': [{'id': l.id, 'old': _q(l.price_subtotal), 'new': s, 'new_total': t}
                      for l, s, t in zip(product_lines, new_subs, new_totals)],
            'changed': new_base != old_base,
        }, None

    # ------------------------------------------------------------------
    # ลงมือแก้
    # ------------------------------------------------------------------
    @api.model
    def _direction(self, line, move, is_tax=False):
        u"""ข้างเดบิต/เครดิตของบรรทัด อ่านจากค่าปัจจุบัน (ใบลดหนี้กับใบแจ้งหนี้กลับข้างกัน)"""
        if _d(line.balance) < 0:
            return Decimal('-1')
        if _d(line.balance) > 0:
            return Decimal('1')
        return Decimal('-1') if move.move_type == 'out_invoice' else Decimal('1')

    @api.model
    def _snapshot(self, move, plan):
        cr = self.env.cr
        line_cols = [c for c in LINE_BASE_COLS + PRODUCT_MIRROR_COLS + TAX_MIRROR_COLS
                     if c in self._columns('account_move_line')]
        line_cols = list(dict.fromkeys(line_cols))
        line_ids = [l['id'] for l in plan['lines']] + [plan['tax_line_id']]
        cr.execute('SELECT id, %s FROM account_move_line WHERE id IN %%s' % ', '.join(line_cols),
                   (tuple(line_ids),))
        lines = {str(r[0]): {c: (float(v) if v is not None else None) for c, v in zip(line_cols, r[1:])}
                 for r in cr.fetchall()}
        move_cols = [c for c in MOVE_BASE_COLS + MOVE_EXTRA_COLS if c in self._columns('account_move')]
        cr.execute('SELECT %s FROM account_move WHERE id = %%s' % ', '.join(move_cols), (move.id,))
        row = cr.fetchone()
        move_vals = {c: (float(v) if v is not None else None) for c, v in zip(move_cols, row)}
        flag_cols = [c for c in CALC_FLAG_COLS if c in self._columns('account_move')]
        flags = {}
        if flag_cols:
            cr.execute('SELECT %s FROM account_move WHERE id = %%s' % ', '.join(flag_cols), (move.id,))
            flags = dict(zip(flag_cols, cr.fetchone()))
        tax_invoices = {}
        if self._columns('account_move_tax_invoice'):
            cr.execute('SELECT id, tax_base_amount, balance FROM account_move_tax_invoice '
                       'WHERE move_line_id = %s', (plan['tax_line_id'],))
            tax_invoices = {str(r[0]): {'tax_base_amount': float(r[1] or 0), 'balance': float(r[2] or 0)}
                            for r in cr.fetchall()}
        return {'lines': lines, 'move': move_vals, 'tax_invoices': tax_invoices, 'flags': flags}

    @api.model
    def _set_calc_flags(self, move_id, flags):
        u"""ตั้งแฟล็กคำนวณของหัวเอกสารและบรรทัด (บรรทัดเก็บสำเนา related store) ด้วย SQL
        — ไม่ผ่าน ORM เพื่อไม่ให้ราคาต่อหน่วย (ถอด VAT) ที่แสดงบนเอกสารถูกคำนวณใหม่"""
        flags = {c: v for c, v in (flags or {}).items() if c in self._columns('account_move')}
        if not flags:
            return
        cols = list(flags)
        sets = ', '.join('%s = %%s' % c for c in cols)
        vals = tuple(bool(flags[c]) for c in cols)
        self.env.cr.execute('UPDATE account_move SET %s WHERE id = %%s' % sets, vals + (move_id,))
        line_cols = [c for c in cols if c in self._columns('account_move_line')]
        if line_cols:
            self.env.cr.execute(
                'UPDATE account_move_line SET %s WHERE move_id = %%s' % ', '.join('%s = %%s' % c for c in line_cols),
                tuple(bool(flags[c]) for c in line_cols) + (move_id,))

    @api.model
    def _update(self, table, rec_id, vals):
        if not vals:
            return
        cols = list(vals)
        self.env.cr.execute('UPDATE %s SET %s WHERE id = %%s' % (table, ', '.join('%s = %%s' % c for c in cols)),
                            tuple(vals[c] for c in cols) + (rec_id,))

    @api.model
    def _check_balanced(self, move):
        self.env.cr.execute("""
            SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0), COALESCE(SUM(amount_currency), 0)
              FROM account_move_line WHERE move_id = %s""", (move.id,))
        debit, credit, amount_currency = self.env.cr.fetchone()
        if _q(debit) != _q(credit) or _q(amount_currency) != 0:
            raise UserError(_(u'ยกเลิกการแก้ %s: สมุดรายวันไม่สมดุล (เดบิต %s / เครดิต %s)')
                            % (move.name, _money(debit), _money(credit)))

    @api.model
    def apply(self, move, source='manual'):
        u"""แก้ใบเดียว คืน log ที่สร้าง (หรือ False ถ้าไม่มีอะไรต้องแก้) — error = UserError"""
        move = move.sudo()
        self.env['account.move'].flush()
        self.env['account.move.line'].flush()
        move.invalidate_cache()
        plan, reason = self.analyze(move)
        if reason:
            raise UserError(u'%s: %s' % (move.name, reason))
        if not plan['changed']:
            return False
        before = self._snapshot(move, plan)
        line_cols = self._columns('account_move_line')
        move_cols = self._columns('account_move')
        lines = {l.id: l for l in move.line_ids}

        # 1) บรรทัดรายได้
        for item in plan['lines']:
            line = lines[item['id']]
            old = before['lines'][str(line.id)]
            sign = self._direction(line, move)
            bal = item['new'] * sign
            vals = {'price_subtotal': item['new'], 'price_total': item['new_total'],
                    'balance': bal, 'amount_currency': bal,
                    'debit': bal if bal > 0 else Decimal('0'), 'credit': -bal if bal < 0 else Decimal('0')}
            for col in PRODUCT_MIRROR_COLS:
                if col in line_cols and old.get(col) is not None \
                        and abs(_d(old[col]) - item['old']) < CENT / 2:
                    vals[col] = item['new']
            self._update('account_move_line', line.id, vals)

        # 2) บรรทัดภาษี
        tax_line = lines[plan['tax_line_id']]
        sign = self._direction(tax_line, move, is_tax=True)
        bal = plan['new_tax'] * sign
        vals = {'price_unit': plan['new_tax'], 'price_subtotal': plan['new_tax'],
                'price_total': plan['new_tax'], 'balance': bal, 'amount_currency': bal,
                'debit': bal if bal > 0 else Decimal('0'), 'credit': -bal if bal < 0 else Decimal('0'),
                'tax_base_amount': plan['new_base']}
        for col in TAX_MIRROR_COLS:
            if col in line_cols:
                vals[col] = plan['new_tax']
        self._update('account_move_line', tax_line.id, vals)

        # 3) หัวเอกสาร (amount_total ไม่แตะ)
        old_move = before['move']
        msign = Decimal('-1') if (old_move.get('amount_untaxed_signed') or 0) < 0 else Decimal('1')
        if not old_move.get('amount_untaxed_signed'):
            msign = Decimal('-1') if move.move_type == 'out_refund' else Decimal('1')
        vals = {'amount_untaxed': plan['new_base'], 'amount_tax': plan['new_tax'],
                'amount_untaxed_signed': plan['new_base'] * msign,
                'amount_tax_signed': plan['new_tax'] * msign}
        if 'amount_price_subtotal_without_discount' in move_cols and \
                old_move.get('amount_price_subtotal_without_discount') is not None and \
                abs(_d(old_move['amount_price_subtotal_without_discount']) - plan['old_base']) < CENT / 2:
            vals['amount_price_subtotal_without_discount'] = plan['new_base']
        if 'wht_amt_net' in move_cols:
            vals['wht_amt_net'] = plan['total']     # ไม่มีหัก ณ ที่จ่าย (ใบที่มีหักถูกข้ามแล้ว)
        if 'target_base_total' in move_cols and 'target_amount_total' in move_cols:
            self.env.cr.execute('SELECT COALESCE(target_amount_total, 0) FROM account_move WHERE id = %s',
                                (move.id,))
            if self.env.cr.fetchone()[0]:
                # ยอดเป้าหมายยังตั้งอยู่ — snapshot ฐานต้องเท่ากับ SUM(price_total) ใหม่ ไม่งั้นระบบล้างเป้าทิ้ง
                vals['target_base_total'] = plan['total']
        self._update('account_move', move.id, vals)

        # 4) รายงานภาษีขาย
        for ti_id, ti in before['tax_invoices'].items():
            tsign = Decimal('-1') if (ti['balance'] < 0 or ti['tax_base_amount'] < 0) else Decimal('1')
            if not ti['balance'] and not ti['tax_base_amount']:
                tsign = Decimal('-1') if move.move_type == 'out_refund' else Decimal('1')
            self._update('account_move_tax_invoice', int(ti_id), {
                'tax_base_amount': plan['new_base'] * tsign, 'balance': plan['new_tax'] * tsign})

        # 5) ปิด Method A/B ของใบนี้ ไม่ให้บันทึกครั้งถัดไปคำนวณทับ (ย้อนกลับได้จาก log)
        self._set_calc_flags(move.id, {c: False for c in CALC_FLAG_COLS})

        self._check_balanced(move)
        self.env['account.move'].invalidate_cache()
        self.env['account.move.line'].invalidate_cache()

        log = self.env['npd.vat.split.fix.log'].sudo().create({
            'move_id': move.id,
            'old_base': float(plan['old_base']), 'old_tax': float(plan['old_tax']),
            'new_base': float(plan['new_base']), 'new_tax': float(plan['new_tax']),
            'total': float(plan['total']),
            'source': source,
            'old_values': json.dumps(before, ensure_ascii=False),
        })
        move.message_post(body=_(
            u'<b>แก้ฐาน/VAT ให้ตรงยอดรวม</b> (%s) โดย %s<br/>'
            u'ยอดก่อน VAT: %s → <b>%s</b><br/>VAT 7%%: %s → <b>%s</b><br/>'
            u'ยอดรวม: %s (ไม่เปลี่ยนแปลง)') % (
                dict(log._fields['source'].selection).get(source), self.env.user.name,
                _money(plan['old_base']), _money(plan['new_base']),
                _money(plan['old_tax']), _money(plan['new_tax']), _money(plan['total'])),
            message_type='notification')
        _logger.info('npd_vat_split_fix: %s (id %s) base %s -> %s, tax %s -> %s [%s]', move.name, move.id,
                     plan['old_base'], plan['new_base'], plan['old_tax'], plan['new_tax'], source)
        return log

    # ------------------------------------------------------------------
    # งานตั้งเวลา: วันที่ 1 เวลา 03:00 ไทย แก้ทั้งเดือนก่อนหน้า
    # ------------------------------------------------------------------
    @api.model
    def _thai_today(self):
        return (fields.Datetime.now() + THAI_OFFSET).date()

    @api.model
    def _cron_fix_previous_month(self):
        today = self._thai_today()
        # cron ยิงทุกวัน 03:00 ไทย ทำงานเฉพาะวันที่ 1 (= คืนสิ้นเดือนที่เพิ่งจบ)
        if today.day != 1 and not self.env.context.get('npd_force_run'):
            return
        first_this = today.replace(day=1)
        date_from = first_this - relativedelta(months=1)
        date_to = first_this - timedelta(days=1)
        icp = self.env['ir.config_parameter'].sudo()
        min_diff = float(icp.get_param('npd_vat_split_fix.cron_min_diff', '0.01') or 0.01)
        ids = self.find_candidates(date_from=date_from, date_to=date_to, min_diff=min_diff)
        done = skipped = 0
        for i, move_id in enumerate(ids, 1):
            move = self.env['account.move'].browse(move_id)
            try:
                with self.env.cr.savepoint():
                    if self.apply(move, source='cron'):
                        done += 1
            except Exception as e:
                skipped += 1
                _logger.info('npd_vat_split_fix cron skip %s: %s', move_id, e)
            if i % 50 == 0:
                self.env.cr.commit()
        _logger.info('npd_vat_split_fix cron %s..%s: แก้ %s ใบ ข้าม %s ใบ', date_from, date_to, done, skipped)


class NpdVatSplitFixLog(models.Model):
    _name = 'npd.vat.split.fix.log'
    _description = 'ประวัติการแก้ฐาน/VAT'
    _order = 'id desc'
    _rec_name = 'move_name'

    move_id = fields.Many2one('account.move', string='เอกสาร', required=True, index=True, ondelete='cascade')
    move_name = fields.Char(related='move_id.name', string='เลขที่', store=True)
    move_type = fields.Selection(related='move_id.move_type', string='ประเภท', store=True)
    move_date = fields.Date(related='move_id.date', string='วันที่เอกสาร', store=True)
    partner_id = fields.Many2one(related='move_id.partner_id', string='ลูกค้า', store=True)
    company_id = fields.Many2one(related='move_id.company_id', store=True)
    old_base = fields.Float('ฐานเดิม', digits=(16, 2))
    old_tax = fields.Float('VAT เดิม', digits=(16, 2))
    new_base = fields.Float('ฐานใหม่', digits=(16, 2))
    new_tax = fields.Float('VAT ใหม่', digits=(16, 2))
    total = fields.Float('ยอดรวม', digits=(16, 2))
    diff = fields.Float('ส่วนต่างฐาน', digits=(16, 2), compute='_compute_diff', store=True)
    source = fields.Selection([('manual', 'แก้จากเมนู'), ('cron', 'ระบบแก้อัตโนมัติสิ้นเดือน')],
                              string='ที่มา', default='manual')
    user_id = fields.Many2one('res.users', string='ผู้แก้', default=lambda self: self.env.user)
    state = fields.Selection([('done', 'แก้แล้ว'), ('undone', 'ย้อนกลับแล้ว')], default='done', string='สถานะ')
    undo_user_id = fields.Many2one('res.users', string='ผู้ย้อนกลับ')
    undo_date = fields.Datetime('วันที่ย้อนกลับ')
    old_values = fields.Text('ค่าเดิม (JSON)')

    @api.depends('old_base', 'new_base')
    def _compute_diff(self):
        for rec in self:
            rec.diff = rec.new_base - rec.old_base

    def action_undo(self):
        engine = self.env['npd.vat.split.fix']
        for log in self.sudo():
            if log.state != 'done':
                continue
            later = self.search([('move_id', '=', log.move_id.id), ('state', '=', 'done'), ('id', '>', log.id)])
            if later:
                raise UserError(_(u'%s ถูกแก้ซ้ำภายหลัง ให้ย้อนกลับรายการล่าสุดก่อน') % log.move_name)
            data = json.loads(log.old_values or '{}')
            self.env['account.move'].flush()
            self.env['account.move.line'].flush()
            for line_id, vals in data.get('lines', {}).items():
                engine._update('account_move_line', int(line_id), vals)
            engine._update('account_move', log.move_id.id, data.get('move', {}))
            for ti_id, vals in data.get('tax_invoices', {}).items():
                engine._update('account_move_tax_invoice', int(ti_id), vals)
            engine._set_calc_flags(log.move_id.id, data.get('flags'))
            engine._check_balanced(log.move_id)
            self.env['account.move'].invalidate_cache()
            self.env['account.move.line'].invalidate_cache()
            log.write({'state': 'undone', 'undo_user_id': self.env.user.id, 'undo_date': fields.Datetime.now()})
            log.move_id.message_post(body=_(u'<b>ย้อนกลับการแก้ฐาน/VAT</b> โดย %s<br/>'
                                            u'ยอดก่อน VAT: %s / VAT: %s (กลับเป็นค่าเดิม)') % (
                self.env.user.name, _money(log.old_base), _money(log.old_tax)), message_type='notification')
        return True

    def action_open_move(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': self.move_id.id,
                'view_mode': 'form', 'target': 'current'}
