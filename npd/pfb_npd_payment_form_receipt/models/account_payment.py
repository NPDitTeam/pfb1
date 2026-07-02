from odoo import models, fields, api, _
from bahttext import bahttext
from decimal import Decimal, ROUND_HALF_UP

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def round_half_up(self, value):
        # ปัดทศนิยม 2 ตำแหน่งแบบ round-half-up (เช่น 353.025 -> 353.03)
        return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    def get_baht_text_form_receipt(self):
        total_untaxed_amount = sum(i.amount_untaxed_signed for i in self.reconciled_invoice_ids)
        total_amount = self.amount - self.round_half_up(total_untaxed_amount * 5 / 100)
        # total_amount = self.total_amount
        return bahttext(total_amount)