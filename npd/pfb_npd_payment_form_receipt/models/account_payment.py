from odoo import models, fields, api, _
from bahttext import bahttext
from decimal import Decimal, ROUND_HALF_UP

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def round_half_up(self, value):
        # ปัดทศนิยม 2 ตำแหน่งแบบ round-half-up (เช่น 353.025 -> 353.03)
        return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    def compute_wht_rent_5(self, untaxed_amount):
        # ภาษีหัก ณ ที่จ่าย 5% (ค่าเช่า)
        # ต้องปัดฐาน (ยอดก่อน VAT) ให้เป็นทศนิยม 2 ตำแหน่งก่อน เพื่อเลี่ยงปัญหา float
        # (เช่น 31015.499999... -> 31015.50) แล้วจึงคิด 5% ปัดแบบ round-half-up
        # ไม่เช่นนั้น 31015.50 * 5 / 100 จะได้ 1550.774999... ปัดลงเป็น 1550.77
        # แต่ค่าที่ถูกต้อง/ตรงกับระบบคือ 1550.775 -> 1550.78
        base = Decimal(str(untaxed_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        wht = (base * Decimal('5') / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return float(wht)

    def get_baht_text_form_receipt(self):
        total_untaxed_amount = sum(i.amount_untaxed_signed for i in self.reconciled_invoice_ids)
        total_amount = self.amount - self.round_half_up(total_untaxed_amount * 5 / 100)
        # total_amount = self.total_amount
        return bahttext(total_amount)