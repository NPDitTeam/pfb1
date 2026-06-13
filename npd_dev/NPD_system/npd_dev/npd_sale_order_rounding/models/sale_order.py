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
        string='ขั้นการปัดเศษ', digits=(16, 4), copy=False,
        help='ขั้นการปัด เช่น 0.10 จะปัดยอดรวมให้ลงตัวทุก 0.10 บาท')
    x_round_method = fields.Selection([
        ('half_up', 'ปัดเข้าใกล้สุด'),
        ('up', 'ปัดขึ้น'),
        ('down', 'ปัดลง'),
    ], string='ทิศทางการปัดเศษ', default='half_up', copy=False)

    @api.depends('order_line.price_total',
                 'x_round_enabled', 'x_round_step', 'x_round_method')
    def _amount_all(self):
        # ให้ Odoo คำนวณยอดปกติก่อน แล้วค่อยปัดเศษทับ
        super(SaleOrder, self)._amount_all()
        for order in self:
            if order.x_round_enabled and order.x_round_step:
                method = ROUND_METHOD_MAP.get(order.x_round_method, 'HALF-UP')
                target = float_round(
                    order.amount_total,
                    precision_rounding=order.x_round_step,
                    rounding_method=method,
                )
                diff = target - order.amount_total
                # ส่วนต่างจากการปัดถูกดูดเข้า amount_tax (amount_untaxed คงเดิม)
                order.amount_total = target
                order.amount_tax = order.amount_tax + diff

    def action_open_rounding_wizard(self):
        self.ensure_one()
        return {
            'name': 'ปัดเศษยอดรวม',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.rounding.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_step_preset': str(self.x_round_step) if self.x_round_step in (0.05, 0.1, 0.25, 0.5, 1.0) else 'custom',
                'default_custom_step': self.x_round_step or 0.10,
                'default_method': self.x_round_method or 'half_up',
            },
        }

    def action_clear_rounding(self):
        for order in self:
            order.write({'x_round_enabled': False, 'x_round_step': 0.0})
        return True
