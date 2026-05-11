from odoo import api, fields, models
from bahttext import bahttext

class AccountVoucher(models.Model):
    _inherit = "account.voucher"

    def get_baht_text_form_receipt(self):
        amount = self.amount
        return bahttext(amount)

