# -*- coding: utf-8 -*-

from odoo import models, fields, api

SALE_COMM_TYPE_SELECTION = [
    ('sale_branch', 'ค่าคอม Sale สาขา'),
    ('sale_headoffice', 'ค่าคอม Sale สำนักงานใหญ่'),
]


class CommissionRateBranchSales(models.Model):
    _name = 'commission.rate.branch.sales'
    _description = 'ตั้งค่าอัตราค่าคอมสาขา/Sales'

    name = fields.Char(string='ชื่อ', default='ค่าเริ่มต้น', required=True)
    comm_type = fields.Selection(
        SALE_COMM_TYPE_SELECTION,
        string='ประเภท',
        required=True,
        default='sale_branch',
    )
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
    def get_rates(self, comm_type='sale_branch'):
        """คืนค่า branch_rate, sales_rate ของประเภทที่ระบุ (default = สาขา)
        ถ้ายังไม่ตั้งค่าประเภทนั้น fallback ไป record แรก แล้ว default 6%, 2%"""
        config = self.search([('comm_type', '=', comm_type)], limit=1)
        if config:
            return config.branch_rate, config.sales_rate
        config = self.search([], limit=1)
        if config:
            return config.branch_rate, config.sales_rate
        return 6.0, 2.0
