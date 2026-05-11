from odoo import models, fields, api, _
from bahttext import bahttext

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def get_baht_text_tax_invoice(self):
        total_amount = self.amount
        return bahttext(total_amount)