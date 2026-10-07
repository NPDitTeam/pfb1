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

    # วันที่เริ่มใช้เลข Tax Invoice Number เป็น "เลขที่" ของใบกำกับภาษี/ใบเสร็จรับเงิน
    # ใบก่อนวันนี้ยังเป็นเลขรันหน้ารับชำระ (ใบที่พิมพ์/ส่งลูกค้าไปแล้วต้องได้เลขเดิม)
    # ปรับได้ที่ ตั้งค่า > ระบบ > System Parameters โดยไม่ต้องแก้โค้ด
    RECEIPT_TAX_NUMBER_PARAM = 'pfb_npd_payment_form_receipt.tax_number_from'
    RECEIPT_TAX_NUMBER_FROM = '2026-10-07'

    def get_form_receipt_number(self):
        """เลขที่ / NO. ของใบกำกับภาษี/ใบเสร็จรับเงิน

        ตั้งแต่วันที่กำหนด และมี Tax Invoice Number (แท็บ Tax Invoice ของรับชำระ)
        → ใช้ Tax Invoice Number; นอกนั้นใช้เลขรันหน้ารับชำระเหมือนเดิม
        """
        self.ensure_one()
        start = self.env['ir.config_parameter'].sudo().get_param(
            self.RECEIPT_TAX_NUMBER_PARAM, self.RECEIPT_TAX_NUMBER_FROM)
        if self.date and str(self.date) >= start:
            numbers = self.tax_invoice_ids.filtered(
                lambda t: t.tax_invoice_number and not t.reversing_id and not t.reversed_id
            ).mapped('tax_invoice_number')
            if numbers:
                return ', '.join(dict.fromkeys(numbers))
        return self.name

    def get_baht_text_form_receipt(self):
        total_untaxed_amount = sum(i.amount_untaxed_signed for i in self.reconciled_invoice_ids)
        total_amount = self.amount - self.round_half_up(total_untaxed_amount * 5 / 100)
        # total_amount = self.total_amount
        return bahttext(total_amount)