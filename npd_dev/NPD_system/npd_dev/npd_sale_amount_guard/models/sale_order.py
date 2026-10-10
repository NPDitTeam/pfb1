# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

_logger = logging.getLogger(__name__)

# ยอดหัวใบกับผลรวมรายการต่างได้ไม่เกินนี้ (บาท) — กันเศษจากการปัด/ล็อกยอดตามใบเสนอราคา
HEADER_TOLERANCE = 1.0
AMOUNT_FIELDS = ('amount_untaxed', 'amount_tax', 'amount_total')
# ช่องในรายการที่ต้องบันทึกประวัติ (มีเฉพาะช่องที่มีอยู่จริงในฐานนั้น)
TRACK_LINE_FIELDS = [
    ('product_uom_qty', 'จำนวน'),
    ('pfb_quantity', 'จำนวนชิ้น'),
    ('price_unit', 'ราคาต่อหน่วย'),
    ('discount', 'ส่วนลด %'),
    ('discount_method', 'วิธีลด'),
    ('discount_amount', 'ส่วนลด'),
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # วันเช่า (pfb_npd_all_customs) ให้ขึ้นประวัติใน chatter
    pfb_date_of_rent = fields.Integer(tracking=True)

    def _npd_lines_untaxed(self):
        self.ensure_one()
        return sum(self.order_line.filtered(lambda l: not l.display_type).mapped('price_subtotal'))

    def _npd_header_mismatch(self):
        self.ensure_one()
        diff = self.amount_untaxed - self._npd_lines_untaxed()
        return diff if abs(diff) > HEADER_TOLERANCE else 0.0

    def _npd_recompute_header(self):
        """ให้ ORM คำนวณยอดหัวใบใหม่จากรายการ (ผ่าน _amount_all ของทุกโมดูล รวมการปัดเศษ)"""
        if not self:
            return
        for fname in AMOUNT_FIELDS:
            self.env.add_to_compute(self._fields[fname], self)
        self.flush(list(AMOUNT_FIELDS))
        self.invalidate_cache(list(AMOUNT_FIELDS), self.ids)

    def _npd_check_header(self, when):
        """ยอดหัวใบต้องตรงผลรวมรายการ: ไม่ตรงคำนวณใหม่ให้ก่อน ยังไม่ตรงจึงบล็อก"""
        bad = self.filtered(lambda o: o._npd_header_mismatch())
        if not bad:
            return
        for order in bad:
            before = order.amount_total
            order._npd_recompute_header()
            if not order._npd_header_mismatch():
                order.message_post(body=_(
                    'ระบบคำนวณยอดหัวใบใหม่ก่อน%(when)s: ยอดหัวใบไม่ตรงผลรวมรายการ '
                    '%(b).2f → %(a).2f') % {'when': when, 'b': before, 'a': order.amount_total})
        still = bad.filtered(lambda o: o._npd_header_mismatch())
        if still:
            o = still[0]
            raise UserError(_(
                '%(name)s: ยอดหัวใบ (ก่อนภาษี %(h).2f) ไม่ตรงผลรวมรายการ (%(l).2f)\n'
                '%(when)sไม่ได้ กรุณาแจ้งฝ่ายบัญชี/IT ตรวจสอบ') % {
                'name': o.name, 'h': o.amount_untaxed, 'l': o._npd_lines_untaxed(), 'when': when})

    def action_confirm(self):
        self._npd_check_header(_('ยืนยันใบสั่งขาย'))
        return super().action_confirm()

    def _create_invoices(self, grouped=False, final=False, date=None):
        self._npd_check_header(_('สร้างใบแจ้งหนี้'))
        return super()._create_invoices(grouped=grouped, final=final, date=date)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ------------------------------------------------------------------
    # ข้อ 5: จำนวนเปลี่ยนตามวันเช่าใน _compute_insurance_price (pfb_npd_all_customs)
    # การเขียนจำนวนกลางการคำนวณทำให้รายการเปลี่ยนแต่ยอดหัวใบค้าง -> สั่งคำนวณหัวใบใหม่
    # ------------------------------------------------------------------
    def _compute_insurance_price(self):
        parent = getattr(super(), '_compute_insurance_price', None)
        if parent is None:
            return None
        before = {line.id: line.product_uom_qty for line in self if line.id}
        res = parent()
        orders = self.filtered(
            lambda l: l.id in before and float_compare(
                before[l.id], l.product_uom_qty, precision_digits=4) != 0
        ).mapped('order_id')
        if orders:
            for fname in AMOUNT_FIELDS:
                self.env.add_to_compute(orders._fields[fname], orders)
        return res

    # ------------------------------------------------------------------
    # ประวัติการแก้ไขรายการ -> chatter ของใบสั่งขาย
    # ------------------------------------------------------------------
    def _npd_tracked_fields(self):
        return [(f, label) for f, label in TRACK_LINE_FIELDS if f in self._fields]

    @staticmethod
    def _npd_fmt(field, value):
        if field.type == 'selection':
            sel = field.selection if isinstance(field.selection, (list, tuple)) else []
            return dict(sel).get(value, value) or '-'
        if field.type in ('float', 'monetary'):
            return '{:,.4f}'.format(value or 0.0).rstrip('0').rstrip('.')
        return value if value not in (False, None) else '-'

    def write(self, vals):
        if self.env.context.get('install_mode') or self.env.context.get('npd_no_line_tracking'):
            return super().write(vals)
        tracked = [(f, label) for f, label in self._npd_tracked_fields() if f in vals]
        if not tracked:
            return super().write(vals)
        old = {line.id: {f: line[f] for f, _l in tracked} for line in self}
        res = super().write(vals)
        changes = {}
        for line in self:
            diffs = []
            for f, label in tracked:
                field = line._fields[f]
                a, b = old[line.id][f], line[f]
                if field.type in ('float', 'monetary'):
                    if float_compare(a or 0.0, b or 0.0, precision_digits=4) == 0:
                        continue
                elif a == b:
                    continue
                diffs.append('%s %s → %s' % (label, self._npd_fmt(field, a), self._npd_fmt(field, b)))
            if diffs:
                changes.setdefault(line.order_id, []).append(
                    '<li>%s: %s</li>' % (line.product_id.display_name or line.name or '', ', '.join(diffs)))
        for order, items in changes.items():
            order.message_post(body=_('<b>แก้ไขรายการ</b><ul>%s</ul>') % ''.join(items))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('install_mode'):
            for order in lines.mapped('order_id').filtered(lambda o: o.state in ('sale', 'done')):
                items = ''.join('<li>%s จำนวน %s ราคา %s</li>' % (
                    l.product_id.display_name or l.name or '', self._npd_fmt(l._fields['product_uom_qty'], l.product_uom_qty),
                    self._npd_fmt(l._fields['price_unit'], l.price_unit))
                    for l in lines.filtered(lambda x: x.order_id == order and not x.display_type))
                if items:
                    order.message_post(body=_('<b>เพิ่มรายการหลังยืนยัน</b><ul>%s</ul>') % items)
        return lines

    def unlink(self):
        if not self.env.context.get('install_mode'):
            for order in self.mapped('order_id'):
                items = ''.join('<li>%s จำนวน %s</li>' % (
                    l.product_id.display_name or l.name or '', self._npd_fmt(l._fields['product_uom_qty'], l.product_uom_qty))
                    for l in self.filtered(lambda x: x.order_id == order and not x.display_type))
                if items:
                    order.message_post(body=_('<b>ลบรายการ</b><ul>%s</ul>') % items)
        return super().unlink()
