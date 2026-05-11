# my_discount_module/models/purchase_order.py
from odoo import models, fields

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_order_discount = fields.Float(
        string='ส่วนลดใบสั่งซื้อ',
        digits='Discount',
        default=0.0
    )