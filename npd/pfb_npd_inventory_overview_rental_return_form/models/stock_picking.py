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


