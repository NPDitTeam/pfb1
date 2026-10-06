from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    use_new_calc = fields.Boolean(
        string='คิดราคาต่อหน่วยแบบถอด Vat',
        default=True,
        copy=True,
        tracking=True,
        help='True = ใช้สูตรใหม่: ราคาต่อหน่วยแสดงแบบถอด VAT แล้ว (UI). '
             'False = ใช้สูตรระบบเดิม. '
             'flag นี้ส่งต่อไปยัง Invoice / Credit Note อัตโนมัติ',
    )

    use_baan_kheaw = fields.Boolean(
        string='ใช้ราคาจากบ้านเขียว',
        default=False,
        copy=True,
        tracking=True,
        help='ติ๊ก = ไม่ใช้ฟังก์ชันคำนวณใหม่ (Method A) เลย และอัพเดทยอด '
             'ด้วยระบบเดิมของ Odoo. ค่านี้ส่งต่อไป invoice อัตโนมัติ',
    )

    vat_from_total = fields.Boolean(
        string='คำนวณ VAT จากยอดรวม',
        default=True,
        copy=True,
        tracking=True,
        help='True (Method B) = amount_tax = round(amount_untaxed × 0.07, 2) '
             'ปัดครั้งเดียวที่ระดับ order. ใช้กับเอกสารใหม่. '
             'False = amount_tax = SUM(line.price_tax) (ปัดรายบรรทัดแบบเดิม) '
             'ใช้กับเอกสารเก่าก่อนเปิดฟีเจอร์นี้. '
             'flag นี้ส่งต่อไปยัง Invoice อัตโนมัติ (POC: SO ก่อน)',
    )

    can_edit_use_new_calc = fields.Boolean(
        compute='_compute_can_edit_use_new_calc',
    )

    @api.depends_context('uid')
    def _compute_can_edit_use_new_calc(self):
        has_perm = self.env.user.can_edit_use_new_calc
        for rec in self:
            rec.can_edit_use_new_calc = has_perm

    @api.onchange('use_new_calc', 'use_baan_kheaw')
    def _onchange_npd_calc_flags(self):
        """รีเฟรช price_unit_no_vat ของทุก line ทันทีใน UI
        invalidate cache แล้วเรียก compute ตรงๆ — ไม่ใช้ line.update()
        เพราะ line.update() จะทำให้ form ส่งค่ากลับ server บน save แล้ว
        trigger inverse → write กลับเข้า price_unit (round-trip drift)"""
        if not self.order_line:
            return
        # invalidate ก่อนแล้วให้ compute ทำงานใหม่ตาม flag ใหม่
        self.order_line.invalidate_cache(['price_unit_no_vat'])
        self.order_line._compute_price_unit_no_vat()

    def _amount_all(self):
        """Method B (vat_from_total) ตอน ORM คำนวณยอดหัวเอกสารเอง

        _npd_force_round_sql เขียน VAT แบบ Method B ลงหัวด้วย SQL ตอนแก้บรรทัด
        แต่หลัง line.write เสร็จ ORM ยัง mark ยอดหัวให้ recompute อีกรอบ
        (modified('order_line') ใน sale.order.write) → ตอน flush ท้าย request
        compute มาตรฐานเขียนทับเป็น SUM(price_tax) รายบรรทัด ทำให้ VAT เพี้ยน
        ±0.01 เคส QT-261006-0007: 28,477.20 → VAT 1,993.41 แทน 1,993.40
        จึงปรับ VAT ตรงนี้ด้วย ไม่ว่า recompute จะเกิดตอนไหนก็ได้ยอดเดียวกับ SQL

        ปรับด้วยส่วนต่าง (delta) จาก SUM(price_tax) แทนการเขียนทับ เพื่อไม่ล้าง
        ส่วนต่างที่โมดูลอื่นบวกไว้ (เช่น ปัดเศษยอดรวม npd_sale_order_rounding)
        ทำเฉพาะ order ที่ทุกบรรทัดที่มียอดมีแต่ภาษี 7% (ไม่มี WHT/ภาษีอื่นปน)
        """
        res = super()._amount_all()
        for order in self:
            if not order.vat_from_total:
                continue
            lines = order.order_line.filtered(lambda l: not l.display_type)
            taxed = lines.filtered(lambda l: l.price_subtotal)
            if not taxed or not all(
                    l.tax_id and all(abs(t.amount - 7.0) < 0.01 for t in l.tax_id)
                    for l in taxed):
                continue
            untaxed = round(sum(lines.mapped('price_subtotal')), 2)
            line_tax = round(sum(lines.mapped('price_tax')), 2)
            delta = round(round(untaxed * 0.07, 2) - line_tax, 2)
            if not delta:
                continue
            order.amount_tax = round(order.amount_tax + delta, 2)
            order.amount_total = round(order.amount_total + delta, 2)
        return res

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        vals['use_new_calc'] = self.use_new_calc
        vals['use_baan_kheaw'] = self.use_baan_kheaw
        vals['vat_from_total'] = self.vat_from_total
        return vals

    def write(self, vals):
        res = super().write(vals)
        if ('use_new_calc' in vals or 'use_baan_kheaw' in vals
                or 'vat_from_total' in vals):
            for order in self:
                order.order_line.with_context(npd_skip_round=True)._npd_recalc_amounts()
        return res

    def copy(self, default=None):
        """ตอนกดซ้ำ (duplicate) flag ต่างๆ ถูกก็อปมาพร้อมค่าเดิม (copy=True)
        จึงไม่ "เปลี่ยนค่า" → write hook ไม่ยิง → Method B (คิด VAT จากยอดรวม)
        ไม่ทำงาน และ amount_tax ที่ _npd_force_round_sql เขียนตอน create line
        ถูก compute มาตรฐานของ Odoo เขียนทับกลับเป็นผลรวมรายบรรทัด
        บังคับ recompute ยอดทั้ง order หลัง copy เพื่อให้ยอดถูกต้อง"""
        new_order = super().copy(default=default)
        if new_order.order_line:
            new_order.order_line.with_context(
                npd_skip_round=True)._npd_recalc_amounts()
        return new_order
