from odoo import api, fields, models
from bahttext import bahttext

class AccountVoucher(models.Model):
    _inherit = "account.voucher"

    def get_baht_text_amount(self):
        amount = self.amount
        return bahttext(amount)

