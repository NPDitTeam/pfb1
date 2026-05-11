# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AllReceivableReport(models.Model):
    _name = 'all.receivable.report'
    _description = 'รายงานลูกหนี้ทั้งหมด'
    _order = 'partner_name, branch_name'
    _rec_name = 'partner_name'

    partner_id = fields.Many2one('res.partner', string='ลูกค้า', ondelete='cascade')
    partner_code = fields.Char(string='รหัสลูกค้า', index=True)
    partner_name = fields.Char(string='ชื่อลูกค้า', index=True)
    partner_phone = fields.Char(string='เบอร์โทรลูกค้า')
    partner_address = fields.Text(string='ที่อยู่ลูกค้า')
    branch_name = fields.Char(string='สาขา', index=True)
    first_debt_date = fields.Date(string='วันที่เริ่มเป็นหนี้')
    last_due_date = fields.Date(string='วันครบกำหนดชำระ')
    rent_amount = fields.Float(string='ค่าเช่า', digits=(12, 2))
    insurance_amount = fields.Float(string='ค่าประกัน', digits=(12, 2))
    lost_penalty_amount = fields.Float(string='ค่าปรับหาย', digits=(12, 2))
    damage_penalty_amount = fields.Float(string='ค่าปรับชำรุด', digits=(12, 2))
    shipping_cost_amount = fields.Float(string='ค่าขนส่ง', digits=(12, 2))
    vat_amount = fields.Float(string='VAT 7%', digits=(12, 2))
    amount_total = fields.Float(string='ยอดรวมทั้งหมด', digits=(12, 2))
    amount_residual = fields.Float(string='ยอดค้างชำระ', digits=(12, 2))
    amount_remaining = fields.Float(string='คงเหลือ', digits=(12, 2))
    invoice_count = fields.Integer(string='จำนวนใบแจ้งหนี้')
