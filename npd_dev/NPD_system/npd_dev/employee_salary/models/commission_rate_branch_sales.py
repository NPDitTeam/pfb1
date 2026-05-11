# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CommissionRateBranchSales(models.Model):
    _name = 'commission.rate.branch.sales'
    _description = 'ตั้งค่าอัตราค่าคอมสาขา/Sales'

    name = fields.Char(string='ชื่อ', default='ค่าเริ่มต้น', required=True)
    branch_rate = fields.Float(
        string='ค่าคอมสาขา (%)',
        digits=(16, 2),
        default=6.0,
        required=True,
    )
    sales_rate = fields.Float(
        string='ค่าคอม Sales (%)',
        digits=(16, 2),
        default=2.0,
        required=True,
    )

    @api.model
    def get_rates(self):
        """คืนค่า branch_rate, sales_rate จาก record แรก (หรือ default 6%, 2%)"""
        config = self.search([], limit=1)
        if config:
            return config.branch_rate, config.sales_rate
        return 6.0, 2.0
