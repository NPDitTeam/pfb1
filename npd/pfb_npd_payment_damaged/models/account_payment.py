from odoo import models, fields, api, _
from bahttext import bahttext

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def get_baht_text_damaged_receipt(self):
        total_amount = self.total_amount
        return bahttext(total_amount)