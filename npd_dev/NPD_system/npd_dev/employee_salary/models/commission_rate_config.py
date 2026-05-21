# -*- coding: utf-8 -*-

from odoo import models, fields, api

SALE_COMM_TYPE_SELECTION = [
    ('sale_branch', 'ค่าคอม Sale สาขา'),
    ('sale_headoffice', 'ค่าคอม Sale สำนักงานใหญ่'),
]


class CommissionRateConfig(models.Model):
    _name = 'commission.rate.config'
    _description = 'ตั้งค่าอัตราคอมมิชชั่น Sales'
    _order = 'comm_type asc, min_amount asc'

    sequence = fields.Integer(string='ลำดับ', default=10)
    comm_type = fields.Selection(
        SALE_COMM_TYPE_SELECTION,
        string='ประเภท',
        required=True,
        default='sale_branch',
    )
    min_amount = fields.Float(string='ยอดขั้นต่ำ', required=True, digits=(16, 2))
    rate = fields.Float(string='อัตราคอมมิชชั่น (%)', required=True, digits=(16, 2))
