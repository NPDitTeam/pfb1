
from odoo import api, fields, models,_



class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    company_id = fields.Many2one('res.company', readonly=True)