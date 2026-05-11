from odoo import models, fields, api, _
from bahttext import bahttext

class SaleOrder(models.Model):
    _inherit = 'stock.picking'

    # def get_baht_text(self):
    #     calc = sum(self.order_line.mapped('pfb_amount'))
    #     sum_amount = self.amount_total + self.pfb_amount
    #     return bahttext(sum_amount)

    def get_baht_text_inventory_overview_rental_return_form(self):
        total_amount = 00.00
        return bahttext(total_amount)

    def get_request_source_location_name(self):
        self.ensure_one()
        request = self.env['stock.request'].search([('name', '=', self.origin)], limit=1)
        return request.location_src_id.name if request and request.location_src_id else "-"

    def get_related_stock_request(self):
        self.ensure_one()
        return self.env['stock.request'].search([('name', '=', self.origin)], limit=1)
