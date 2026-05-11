from odoo import models, fields

class ShipmentInformation(models.Model):
    _inherit = 'sale.order'

    delivery_employee_id = fields.Many2one('hr.employee', string='พนังานส่งของ')
    destination = fields.Text(string='ปลายทาง')
    shipping_cost = fields.Float(string='ค่าขนส่ง')
    distance_km = fields.Float(string='ระยะทาง (km)')
