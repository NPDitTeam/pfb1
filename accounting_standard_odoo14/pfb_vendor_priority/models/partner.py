from odoo import models, fields, api


class ProductSupplierInfo(models.Model):
    _inherit = "product.supplierinfo"


    priority_id = fields.Many2one(
        "partner.priority",
        related='name.priority_id',
    )