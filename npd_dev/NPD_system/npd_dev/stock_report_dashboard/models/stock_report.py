from odoo import models, fields, api


class RentalProductReport(models.Model):
    _name = 'dev_rental.product.report'
    _description = 'Rental Product Report'
    _order = 'product_code, branch'

    product_code = fields.Char(string="รหัสสินค้า")
    product_name = fields.Char(string="รายการสินค้า")
    stock_initial = fields.Float(string="สินค้าตั้งต้น")
    stock_available = fields.Float(string="สินค้าคงเหลือ")
    available_quantity = fields.Float(string="สินค้าถูกจอง")
    stock_in = fields.Float(string="สินค้าถูกเช่า")
    stock_out = fields.Float(string="สินค้าปรับหาย")
    damaged_product = fields.Float(string="สินค้าชำรุด")
    rental_price_day = fields.Float(string="ค่าเช่า/วัน")
    rental_price_month = fields.Float(string="ค่าเช่า/เดือน")
    insurance = fields.Float(string="ค่าประกัน")
    sale_penalty = fields.Float(string="ค่าปรับหาย")
    weight = fields.Float(string="น้ำหนัก")
    branch = fields.Char(string="สาขา")

    # ลบ generate_report_data ออก