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
        ('custom', 'กำหนดเอง (ปรับยอด +/-)'),
    ], string='ขั้นการปัด', default='0.1', required=True)
    custom_step = fields.Float(
        string='กำหนดขั้นเอง (+ เพิ่ม / - ลด)', digits=(16, 2), default=0.0,
        help='จำนวนเงินที่ต้องการบวก/ลบจากยอดรวม เช่น -0.01 คือลด 1 สตางค์, '
             '0.50 คือเพิ่ม 50 สตางค์ (ไม่ใช่ขั้นการปัด จึงลดทีละสตางค์ได้)')

    preview_total = fields.Monetary(
        string='ยอดรวมหลังปัด', compute='_compute_preview',
        currency_field='currency_id')

    def _base_total(self):
        """ยอดฐานจริงก่อนปัด/ปรับ — คิดจากรายการสินค้า ไม่ใช่ยอดที่ถูกปัดไว้แล้ว
        ทำให้พรีวิวตรงกับผลลัพธ์จริงเสมอ แม้เปิด wizard ซ้ำบนใบที่ปรับไปแล้ว"""
        self.ensure_one()
        untaxed, tax = self.order_id._npd_base_amounts()
        return untaxed + tax

    @api.depends('order_id', 'current_total', 'method', 'step_preset', 'custom_step')
    def _compute_preview(self):
        for w in self:
            if not w.order_id:
                w.preview_total = w.current_total
                continue
            base_total = w._base_total()
            if w.step_preset == 'custom':
                # ปรับยอดเอง: บวก/ลบจากยอดฐานตรงๆ ไม่ปัดตามขั้น
                w.preview_total = float_round(
                    base_total + w.custom_step, precision_digits=2)
            else:
                method = ROUND_METHOD_MAP.get(w.method, 'HALF-UP')
                w.preview_total = float_round(
                    base_total, precision_rounding=float(w.step_preset),
                    rounding_method=method)

    def action_apply(self):
        self.ensure_one()
        if self.step_preset == 'custom':
            step, method = self.custom_step, 'adjust'
        else:
            step, method = float(self.step_preset), self.method
        self.order_id.write({
            'x_round_enabled': True,
            'x_round_step': step,
            'x_round_method': method,
        })
        # เขียนยอดที่ปัดแล้วลงตรงๆ (ไม่พึ่ง recompute เพราะ trigger อาจไม่ทำงาน)
        self.order_id._apply_total_rounding()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
