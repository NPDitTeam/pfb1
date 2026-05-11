from odoo import models, fields, api


class MonthlyPenaltyReport(models.Model):
    _name = 'monthly.penalty.report.may'
    _description = 'สรุปรายงานหนี้ค้างชำระ'
    _order = 'report_date desc'

    report_date = fields.Date(string='วดป')
    soo = fields.Char(string='เลขใบกำกับเช่า')
    rental_amount = fields.Float(string='ค่าเช่าสินค้า')
    vat = fields.Float(string='VAT')
    insurance = fields.Float(string='ค่าประกัน')
    damage_penalty = fields.Float(string='ค่าปรับชำรุด')
    lost_penalty = fields.Float(string='ค่าปรับหาย')
    rental_discount = fields.Float(string='ส่วนลดค่าเช่า')
    line_discount = fields.Float(string='ส่วนลดปรับหาย')
    net_rental_fee = fields.Float(string='ค่าเช่าสุทธิ')

    rental_payment_amount = fields.Float(string="รับชำระหนี้ค่าเช่า")
    vat_rental_payment_amount = fields.Float(string="VAT")
    lost_payment_amount = fields.Float(string="รับชำระหนี้ค่าปรับหาย")
    damaged_payment_amount = fields.Float(string="รับชำระหนี้ค่าปรับชำรุด")

    rental_unpaid_amount = fields.Float(string="ค้างชำระค่าเช่า")
    vat_rental_unpaid_amount = fields.Float(string="ค้าง VAT")
    lost_unpaid_amount = fields.Float(string="ค้างชำระค่าปรับหาย")
    damaged_unpaid_amount = fields.Float(string="ค้างชำระค่าปรับชำรุด")
    difference = fields.Float(string="ส่วนต่าง")

    # ลบ search_read และ generate_report ออก