# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import float_round

# map ค่าทิศทางการปัดของเรา -> rounding_method ของ Odoo
ROUND_METHOD_MAP = {
    'half_up': 'HALF-UP',  # ปัดเข้าใกล้สุด เช่น 3744.18 -> 3744.20
    'up': 'UP',            # ปัดขึ้นเสมอ
    'down': 'DOWN',        # ปัดลงเสมอ
}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_round_enabled = fields.Boolean(
        string='เปิดใช้ปัดเศษยอดรวม', copy=False, default=False)
    x_round_step = fields.Float(
        string='ขั้นการปัดเศษ / จำนวนที่ปรับ', digits=(16, 4), copy=False,
        help='โหมดปัดตามขั้น: ขั้นการปัด เช่น 0.10 จะปัดยอดรวมให้ลงตัวทุก 0.10 บาท\n'
             'โหมดปรับยอดเอง: จำนวนเงินที่บวก/ลบจากยอดรวม เช่น -0.01 คือลด 1 สตางค์')
    x_round_method = fields.Selection([
        ('half_up', 'ปัดเข้าใกล้สุด'),
        ('up', 'ปัดขึ้น'),
        ('down', 'ปัดลง'),
        ('adjust', 'ปรับยอดเอง'),
    ], string='ทิศทางการปัดเศษ', default='half_up', copy=False)

    def _npd_target_total(self, base_total):
        """ยอดรวมเป้าหมายหลังปัด/ปรับ ตามการตั้งค่าของใบสั่งขายนี้

        มี 2 โหมด แยกด้วย x_round_method:
        - 'adjust'  : ปรับยอดเอง -> base_total + x_round_step (บวก=เพิ่ม, ลบ=ลด)
        - อื่นๆ      : ปัดตามขั้น -> ปัด base_total ให้ลงตัวทุก x_round_step
        """
        self.ensure_one()
        if not self.x_round_enabled:
            return base_total
        if self.x_round_method == 'adjust':
            return float_round(base_total + self.x_round_step, precision_digits=2)
        if self.x_round_step:
            method = ROUND_METHOD_MAP.get(self.x_round_method, 'HALF-UP')
            return float_round(
                base_total,
                precision_rounding=self.x_round_step,
                rounding_method=method,
            )
        return base_total

    @api.depends('order_line.price_total',
                 'x_round_enabled', 'x_round_step', 'x_round_method')
    def _amount_all(self):
        # ให้ Odoo คำนวณยอดปกติก่อน แล้วค่อยปัดเศษทับ
        # (เป็น best-effort กรณีรายการสินค้าเปลี่ยนแล้ว recompute ถูก trigger)
        super(SaleOrder, self)._amount_all()
        for order in self:
            if not order.x_round_enabled:
                continue
            target = order._npd_target_total(order.amount_total)
            diff = target - order.amount_total
            # ส่วนต่างจากการปัดถูกดูดเข้า amount_tax (amount_untaxed คงเดิม)
            order.amount_total = target
            order.amount_tax = order.amount_tax + diff

    def _npd_base_amounts(self):
        """ยอดฐานจริงก่อนปัดเศษ คำนวณจากรายการสินค้าโดยตรง
        (กัน drift เวลาปัดซ้ำ เพราะไม่อ่านจากยอดที่ถูกปัดไว้แล้ว)."""
        self.ensure_one()
        untaxed = sum(self.order_line.mapped('price_subtotal'))
        tax = sum(self.order_line.mapped('price_tax'))
        return untaxed, tax

    def _apply_total_rounding(self):
        """เขียนยอดที่ปัดเศษแล้วลง amount_total / amount_tax โดยตรง

        ในระบบนี้มีโมดูล custom override _amount_all ทับ ทำให้ @api.depends
        ของเราไม่ทริกเกอร์ recompute เมื่อเปลี่ยนค่า x_round_* — จึงต้องเขียน
        ยอดลงตรงๆ เหมือนวิธี SQL เดิม ส่วนต่างจากการปัดดูดเข้า amount_tax
        (amount_untaxed คงเดิมตามรายการสินค้า)
        """
        # เคลียร์ recompute ของ amount ที่ค้างอยู่ (จากการ write x_round_*) ให้ลง DB
        # ก่อน ไม่งั้น flush ตอนจบ request จะคำนวณ amount ใหม่มาเขียนทับค่า SQL ของเรา
        self.flush(['amount_untaxed', 'amount_tax', 'amount_total'])
        for order in self:
            untaxed, tax = order._npd_base_amounts()
            base_total = untaxed + tax
            # ปิดการปัด -> _npd_target_total คืนยอดฐานจริง ส่วนต่างเป็น 0
            target = order._npd_target_total(base_total)
            new_tax = float_round(tax + (target - base_total), precision_digits=2)
            new_total = float_round(target, precision_digits=2)
            new_untaxed = float_round(untaxed, precision_digits=2)
            # เขียนลง DB ตรงๆ ด้วย SQL (วิธีที่พิสูจน์แล้วว่าได้ผล) แทนการ write()
            # ลง stored computed field ซึ่ง ORM อาจเมิน
            order.env.cr.execute(
                "UPDATE sale_order "
                "SET amount_untaxed=%s, amount_tax=%s, amount_total=%s "
                "WHERE id=%s",
                (new_untaxed, new_tax, new_total, order.id),
            )
        self.invalidate_cache(
            ['amount_untaxed', 'amount_tax', 'amount_total'], self.ids)

    def action_open_rounding_wizard(self):
        self.ensure_one()
        if self.x_round_method == 'adjust':
            # เคยปรับยอดเอง -> เปิดกลับมาที่โหมดเดิมพร้อมจำนวนที่ปรับไว้
            preset, custom = 'custom', self.x_round_step
        elif self.x_round_step in (0.05, 0.1, 0.25, 0.5, 1.0):
            preset, custom = str(self.x_round_step), 0.0
        else:
            preset, custom = '0.1', 0.0
        return {
            'name': 'ปัดเศษยอดรวม',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.rounding.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_step_preset': preset,
                'default_custom_step': custom,
                'default_method': self.x_round_method if self.x_round_method in ROUND_METHOD_MAP else 'half_up',
            },
        }

    def action_clear_rounding(self):
        for order in self:
            order.write({
                'x_round_enabled': False,
                'x_round_step': 0.0,
                'x_round_method': 'half_up',
            })
            order._apply_total_rounding()
        return True
