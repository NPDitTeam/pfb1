# -*- coding: utf-8 -*-
import re
import base64
import logging
from decimal import Decimal, ROUND_HALF_UP

from odoo import models
from bahttext import bahttext

_logger = logging.getLogger(__name__)

# สมุดรายวันของ "ใบแจ้งหนี้ค่าประกัน" (ระบบสร้างใบนี้ให้อัตโนมัติเมื่อมีค่าประกัน)
DEPOSIT_JOURNAL = u'สมุดรายวันค่าประกัน'


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ------------------------------------------------------------------
    # หมายเหตุสำคัญ: โมดูลใบวางบิล "ค่าเช่า" (pfb_npd_sale_form_Billing_sheet_rent)
    # ก็ inherit sale.order เหมือนกัน Odoo จะรวมเป็นคลาสเดียว -> เมธอดชื่อซ้ำจะทับกัน
    # จึงตั้งชื่อเมธอดของใบวางบิล "ค่าประกัน" ให้ลงท้าย _deposit ทุกตัว (ไม่ชนกัน)
    #
    # ใบวางบิลค่าประกันไม่คิดภาษีหัก ณ ที่จ่าย 5% -> ชำระเต็มจำนวนเสมอ
    # (ค่าประกันไม่ใช่รายได้ จึงไม่ถูกหัก ณ ที่จ่าย) จึงไม่ยุ่งกับ wht_5_percent
    # ------------------------------------------------------------------

    def _deposit_invoice(self):
        """ใบแจ้งหนี้ค่าประกัน (INS) ของใบสั่งขายนี้

        สำคัญ: ใบค่าประกัน "ไม่ได้" ถูกสร้างจากบรรทัดสินค้าของใบสั่งขาย จึง **ไม่อยู่ใน
        self.invoice_ids** (บนฟอร์ม SO จะเห็นปุ่ม "รับเงินประกัน" แยกจากปุ่ม "ใบแจ้งหนี้")
        ตัวเชื่อมจริงคือ account.move.invoice_origin = ชื่อใบสั่งขาย + อยู่ในสมุดรายวันค่าประกัน
        """
        self.ensure_one()
        return self.env['account.move'].search([
            ('invoice_origin', '=', self.name),
            ('move_type', '=', 'out_invoice'),
            ('state', '!=', 'cancel'),
            ('journal_id.name', '=', DEPOSIT_JOURNAL),
        ], order='id desc', limit=1)

    # ------------------------------------------------------------------
    # ยอดเงิน (เฉพาะค่าประกัน)
    # ------------------------------------------------------------------
    def get_deposit_amount(self):
        """ยอดค่าประกันที่ต้องชำระ
        ใช้ยอดจากใบแจ้งหนี้ค่าประกัน (INS) ถ้ามี ไม่งั้น fallback เป็นค่าประกันสุทธิบนใบสั่งขาย
        """
        inv = self._deposit_invoice()
        amount = inv.amount_total if inv else (self.pfb_amount or 0.0)
        return float(Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    def get_total_baht_text_sheet_deposit(self):
        """จำนวนเงิน (ตัวอักษร) ของค่าประกัน"""
        return bahttext(self.get_deposit_amount())

    # ------------------------------------------------------------------
    # Bill Payment: Comp Code / Ref
    # ------------------------------------------------------------------
    def get_comp_code_deposit(self):
        """Comp Code / Biller ID ที่ธนาคารกำหนด (ตั้งค่าที่บริษัท)"""
        return (self.company_id.bill_payment_biller_id or '').strip()

    def _bill_ref1_deposit(self):
        """Ref1 = เลขที่ "ใบแจ้งหนี้ค่าประกัน" (INS-...) เฉพาะตัวเลข

        สำคัญ: ต้องอ้างใบ INS ไม่ใช่ใบค่าเช่า (INV) เพราะเมื่อลูกค้าชำระผ่าน Bill Payment
        ธนาคารจะส่งเลขนี้กลับมา ระบบรับชำระอัตโนมัติ (SCB) จะได้จับคู่ใบค่าประกันถูกใบ
        และลงสมุดรายวันรับชำระค่าประกันให้อัตโนมัติ
        """
        inv = self._deposit_invoice()
        ref = (inv.name if inv else self.name) or ''
        digits = re.sub(r'\D', '', ref)
        return digits or re.sub(r'\D', '', self.name or '')

    def _bill_ref2_deposit(self):
        """Ref2 = เลขผู้เสียภาษีลูกค้า (เฉพาะตัวเลข)"""
        return re.sub(r'\D', '', self.partner_id.vat or '')

    def _bill_amount_satang_deposit(self):
        """ยอดเงินหน่วยสตางค์ (จำนวนเต็ม) สำหรับบาร์โค้ด"""
        amt = Decimal(str(self.get_deposit_amount())).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return str(int((amt * 100).to_integral_value()))

    # ------------------------------------------------------------------
    # Bill Payment: Barcode (มาตรฐานบาร์โค้ดชำระเงินของธนาคารไทย - Code128)
    #   รูปแบบ:  |BillerID \r Ref1 \r Ref2 \r Amount(สตางค์)
    # ------------------------------------------------------------------
    def get_bill_payment_barcode_value_deposit(self):
        biller = self.get_comp_code_deposit()
        if not biller:
            return ''
        return u"|%s\r%s\r%s\r%s" % (
            biller, self._bill_ref1_deposit(), self._bill_ref2_deposit(),
            self._bill_amount_satang_deposit())

    def get_bill_payment_barcode_image_deposit(self):
        value = self.get_bill_payment_barcode_value_deposit()
        if not value:
            return ''
        try:
            img = self.env['ir.actions.report'].barcode(
                'Code128', value, width=560, height=90, humanreadable=0, quiet=1)
            return base64.b64encode(img).decode('ascii')
        except Exception as e:  # noqa: BLE001
            _logger.warning("deposit bill payment barcode error: %s", e)
            return ''

    # ------------------------------------------------------------------
    # Bill Payment: QR (มาตรฐาน EMVCo / Thai QR Bill Payment)
    # ------------------------------------------------------------------
    @staticmethod
    def _emv_tlv_deposit(tag, value):
        return '%s%02d%s' % (tag, len(value), value)

    @staticmethod
    def _emv_crc16_deposit(payload):
        """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)"""
        crc = 0xFFFF
        for ch in payload.encode('utf-8'):
            crc ^= ch << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc = crc << 1
                crc &= 0xFFFF
        return '%04X' % crc

    def get_bill_payment_qr_payload_deposit(self):
        biller = self.get_comp_code_deposit()
        if not biller:
            return ''
        ref1 = self._bill_ref1_deposit()
        ref2 = self._bill_ref2_deposit()
        amount = '%.2f' % self.get_deposit_amount()

        # Tag 30: Bill Payment (merchant account information)
        merchant = self._emv_tlv_deposit('00', 'A000000677010112')  # AID Bill Payment
        merchant += self._emv_tlv_deposit('01', biller)             # Biller ID / Comp Code
        merchant += self._emv_tlv_deposit('02', ref1)               # Reference 1
        if ref2:
            merchant += self._emv_tlv_deposit('03', ref2)           # Reference 2

        payload = self._emv_tlv_deposit('00', '01')                 # Payload Format Indicator
        payload += self._emv_tlv_deposit('01', '12')                # Point of Initiation (12 = มียอด)
        payload += self._emv_tlv_deposit('30', merchant)            # Bill Payment
        payload += self._emv_tlv_deposit('53', '764')               # Currency THB
        payload += self._emv_tlv_deposit('54', amount)              # Amount
        payload += self._emv_tlv_deposit('58', 'TH')                # Country
        payload += '6304'                                           # CRC tag + length
        payload += self._emv_crc16_deposit(payload)
        return payload

    def get_bill_payment_qr_image_deposit(self):
        payload = self.get_bill_payment_qr_payload_deposit()
        if not payload:
            return ''
        try:
            img = self.env['ir.actions.report'].barcode(
                'QR', payload, width=180, height=180)
            return base64.b64encode(img).decode('ascii')
        except Exception as e:  # noqa: BLE001
            _logger.warning("deposit bill payment QR error: %s", e)
            return ''
