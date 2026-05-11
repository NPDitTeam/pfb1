# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    wht_category_id = fields.Many2one(
        comodel_name='wht.category',
        string='หมวดหมู่ WHT',
        help='หมวดหมู่ภาษีหัก ณ ที่จ่าย สำหรับสินค้า/บริการนี้',
    )
    wht_rate_display = fields.Selection(
        related='wht_category_id.wht_rate',
        string='อัตรา WHT',
        readonly=True,
    )

    @api.onchange('wht_category_id')
    def _onchange_wht_category_id(self):
        """เมื่อเปลี่ยนหมวดหมู่ WHT แสดงข้อมูลอัตราที่เกี่ยวข้อง"""
        pass
