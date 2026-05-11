from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError

class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    customer_id = fields.Many2one('res.partner', string='Customer')