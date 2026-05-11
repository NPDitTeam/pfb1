# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CommissionRateConfig(models.Model):
    _name = 'commission.rate.config'
    _description = 'ตั้งค่าอัตราคอมมิชชั่น Sales'
    _order = 'min_amount asc'

    sequence = fields.Integer(string='ลำดับ', default=10)
    min_amount = fields.Float(string='ยอดขั้นต่ำ', required=True, digits=(16, 2))
    rate = fields.Float(string='อัตราคอมมิชชั่น (%)', required=True, digits=(16, 2))
