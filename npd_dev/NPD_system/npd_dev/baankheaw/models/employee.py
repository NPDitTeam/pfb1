from odoo import models, fields

class BaankheawEmployee(models.Model):
    _name = 'baankheaw.employee'
    _description = 'ข้อมูลพนักงานบ้านเขียว'

    emp_code = fields.Char(string='รหัสพนักงาน', required=True)
    name = fields.Char(string='ชื่อพนักงาน', required=True)
    phone = fields.Char(string='เบอร์โทรศัพท์')
    department = fields.Selection([
        ('admin', 'ฝ่ายธุรการ'),
        ('sale', 'ฝ่ายขาย'),
        ('tech', 'ฝ่ายช่าง'),
        ('stock', 'ฝ่ายคลังสินค้า'),
    ], string='แผนก', required=True)
    active = fields.Boolean(string='ใช้งานอยู่', default=True)
