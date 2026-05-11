from odoo import models, fields, api, _
from bahttext import bahttext

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # def get_baht_text(self):
    #     calc = sum(self.order_line.mapped('pfb_amount'))
    #     sum_amount = self.amount_total + self.pfb_amount
    #     return bahttext(sum_amount)

    def get_baht_text_rental_quatation(self):
        total_amount = self.amount_total + self.pfb_amount
        if not total_amount:
            return "0 บาท"
        text = bahttext(total_amount)
        satang = round((total_amount - int(total_amount)) * 100)
        if satang == 1:
            text = text.replace('เอ็ดสตางค์', 'หนึ่งสตางค์')
        return text


