# -*- coding: utf-8 -*-
from odoo import models, fields, api


class TaxReceivableReport(models.Model):
    _name = 'tax.receivable.report'
    _description = 'รายงานลูกหนี้ค้าง Tax'
    _order = 'partner_name'
    _rec_name = 'partner_name'

    partner_id = fields.Many2one('res.partner', string='ลูกค้า', ondelete='cascade')
    partner_code = fields.Char(string='รหัสลูกค้า', index=True)
    partner_name = fields.Char(string='ชื่อลูกค้า', index=True)
    partner_phone = fields.Char(string='เบอร์โทรลูกค้า')
    partner_address = fields.Text(string='ที่อยู่ลูกค้า')
    withholding_tax_amount = fields.Float(string='หัก ณ ที่จ่าย', digits=(12, 2))
