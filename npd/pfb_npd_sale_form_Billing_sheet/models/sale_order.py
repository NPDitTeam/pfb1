from odoo import api, fields, models
from bahttext import bahttext

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def get_date_baht_text(self):
        return bahttext(self.commitment_date)

    def get_rent_daily(self):
        number = 0
        for line in self.order_line:
            number += line.price_unit * line.product_uom_qty
        return number

    def get_total_baht_text_sheet(self):
        if self.deposit_ref:
            total_amount = self.amount_total
        else:
            total_amount = self.pfb_amount + self.amount_total
        # print("deposit_ref",self.deposit_ref)
        # print("total_amount", total_amount)
        return bahttext(total_amount)

