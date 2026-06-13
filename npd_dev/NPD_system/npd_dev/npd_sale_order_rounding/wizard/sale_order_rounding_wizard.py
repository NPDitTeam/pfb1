# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import float_round

from odoo.addons.npd_sale_order_rounding.models.sale_order import ROUND_METHOD_MAP


class SaleOrderRoundingWizard(models.TransientModel):
    _name = 'sale.order.rounding.wizard'
    _description = 'ปัดเศษยอดรวม Sale Order'

    order_id = fields.Many2one(
        'sale.order', string='ใบสั่งขาย', required=True, ondelete='cascade')
    currency_id = fields.Many2one(
        related='order_id.currency_id', readonly=True)
    current_total = fields.Monetary(
        string='ยอดรวมปัจจุบัน', related='order_id.amount_total',
        currency_field='currency_id', readonly=True)

    method = fields.Selection([
        ('half_up', 'ปัดเข้าใกล้สุด'),
        ('up', 'ปัดขึ้น'),
        ('down', 'ปัดลง'),
    ], string='ทิศทางการปัด', default='half_up', required=True)

    step_preset = fields.Selection([
        ('0.05', '0.05'),
        ('0.1', '0.10'),
        ('0.25', '0.25'),
        ('0.5', '0.50'),
        ('1.0', '1.00'),
        ('custom', 'กำหนดเอง'),
    ], string='ขั้นการปัด', default='0.1', required=True)
    custom_step = fields.Float(
        string='กำหนดขั้นเอง', digits=(16, 4), default=0.10)

    preview_total = fields.Monetary(
        string='ยอดรวมหลังปัด', compute='_compute_preview',
        currency_field='currency_id')

    def _get_step(self):
        self.ensure_one()
        if self.step_preset == 'custom':
            return self.custom_step
        return float(self.step_preset)

    @api.depends('current_total', 'method', 'step_preset', 'custom_step')
    def _compute_preview(self):
        for w in self:
            step = w._get_step()
            if step:
                method = ROUND_METHOD_MAP.get(w.method, 'HALF-UP')
                w.preview_total = float_round(
                    w.current_total, precision_rounding=step,
                    rounding_method=method)
            else:
                w.preview_total = w.current_total

    def action_apply(self):
        self.ensure_one()
        step = self._get_step()
        self.order_id.write({
            'x_round_enabled': True,
            'x_round_step': step,
            'x_round_method': self.method,
        })
        return {'type': 'ir.actions.act_window_close'}
