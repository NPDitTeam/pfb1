
from odoo import api, fields, models,_



class SaleOrder(models.Model):
    _inherit = 'sale.order'

    company_id = fields.Many2one('res.company', readonly=True)