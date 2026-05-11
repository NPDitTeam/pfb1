from odoo import models, fields

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    next_review = fields.Date(string="Next Review Date")

class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    next_review = fields.Date(string="Next Review Date")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    next_review = fields.Date(string="Next Review Date")