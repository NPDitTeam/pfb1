from odoo import models, fields, api, _
from bahttext import bahttext

class AccountPayment(models.Model):
    _inherit = 'account.move'

    def get_baht_text_debt_reduction(self):
        discount_taken = self.wht_amt_net - self.amount_tax
        return bahttext(discount_taken)