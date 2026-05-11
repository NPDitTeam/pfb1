# models/purchase_order.py

from odoo import models, fields

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    x_custom_field1 = fields.Char(string="Custom Field 1")
    x_custom_field2 = fields.Char(string="Custom Field 2")
