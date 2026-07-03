from odoo import models
from bahttext import bahttext


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def get_baht_text(self, amount):
        return bahttext(round(amount, 2))
