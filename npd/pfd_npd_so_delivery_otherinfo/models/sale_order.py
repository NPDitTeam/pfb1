from odoo import api, fields, models, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    driver = fields.Char(string='Driver')
    vehicle_type = fields.Char(string='Vehicle Type')
    vehicle_registration = fields.Char(string='Vehicle Registration')

