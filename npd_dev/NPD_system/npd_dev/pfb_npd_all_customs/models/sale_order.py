from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    pfb_so_type = fields.Selection([
        ('sale', 'Sales'),
        ('rent', 'Rent')],
        string="Sale Type",
        index=True, default='sale', required=True)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    pfb_so_rent_ok = fields.Boolean('Can be Rent', compute="_compute_so_rent_ok", store=True)

    @api.depends('order_id', 'order_id.pfb_so_type')
    def _compute_so_rent_ok(self):

        for so_line in self:
            if so_line.order_id.pfb_so_type == 'sale':
                so_line.pfb_so_rent_ok = 0
            else:
                so_line.pfb_so_rent_ok = 1



