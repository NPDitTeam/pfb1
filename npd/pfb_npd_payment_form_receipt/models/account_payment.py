from odoo import models, fields, api, _
from bahttext import bahttext

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def get_baht_text_form_receipt(self):
        total_untaxed_amount = sum(i.amount_untaxed_signed for i in self.reconciled_invoice_ids)
        total_amount = self.amount - total_untaxed_amount * 5 / 100
        # total_amount = self.total_amount
        return bahttext(total_amount)