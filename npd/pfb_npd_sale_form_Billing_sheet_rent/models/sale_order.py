# -*- coding: utf-8 -*-
import re
import base64
import logging
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models
from bahttext import bahttext

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ติ๊ก = ลูกค้าหักภาษี ณ ที่จ่าย 5% -> QR/บาร์โค้ด/Comp Code คิดจากยอดสุทธิ (หัก 5%)
    # ไม่ติ๊ก (ค่าเริ่มต้น) = แสดงยอดเต็ม
    wht_5_percent = fields.Boolean(
        string=u"ภาษีหัก ณ ที่จ่าย 5%",
        default=False,
        help=u"ถ้าติ๊ก: QR/บาร์โค้ด/Comp Code จะคิดจากยอดที่ถูกหัก ณ ที่จ่าย 5% (ยอดสุทธิ). "
             u"ถ้าไม่ติ๊ก: แสดงยอดเต็ม")

    # ------------------------------------------------------------------
    # ยอดเงิน
    # ------------------------------------------------------------------
    def get_wht_amount(self):
        # ภาษีหัก ณ ที่จ่าย 5% ปัดแบบ round-half-up (เช่น 353.025 -> 353.03)
        base = Decimal(str(self.amount_untaxed))
        wht = (base * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return float(wht)

    def get_billing_amount(self):
        """ยอดสำหรับชำระ (QR/บาร์โค้ด): ยอดสุทธิถ้าติ๊กหัก 5%, ยอดเต็มถ้าไม่ติ๊ก"""
        total = Decimal(str(self.amount_total))
        if self.wht_5_percent:
            total = total - Decimal(str(self.get_wht_amount()))
        return float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    def get_date_baht_text(self):
        return bahttext(self.commitment_date)

    def get_rent_daily(self):
        number = 0
        for line in self.order_line:
            number += line.price_unit * line.product_uom_qty
        return number

    def get_total_baht_text_sheet_rent(self):
        # เฉพาะค่าเช่า (ตัดค่าประกันออก) และใช้ยอดสุทธิถ้าติ๊กหักภาษี ณ ที่จ่าย 5%
        # หมายเหตุ: ตั้งชื่อใหม่ (มี _rent) เพื่อไม่ให้ทับเมธอดชื่อเดียวกันของโมดูลใบวางบิลเดิม
        # ที่ inherit sale.order เหมือนกัน (Odoo รวมเป็นคลาสเดียว เมธอดชื่อซ้ำจะทับกัน)
        return bahttext(self.get_billing_amount())

    # ------------------------------------------------------------------
    # Bill Payment: Comp Code / Ref
    # ------------------------------------------------------------------
    def get_comp_code(self):
        """Comp Code / Biller ID ที่ธนาคารกำหนด (ตั้งค่าที่บริษัท)"""
        return (self.company_id.bill_payment_biller_id or '').strip()

    def _bill_ref1(self):
        """Ref1 = เลขที่ใบแจ้งหนี้ (เฉพาะตัวเลข) ถ้าไม่มีใช้เลขใบสั่งขาย"""
        inv = self.invoice_ids[:1]
        ref = (inv.name if inv else self.name) or ''
        digits = re.sub(r'\D', '', ref)
        return digits or re.sub(r'\D', '', self.name or '')

    def _bill_ref2(self):
        """Ref2 = เลขผู้เสียภาษีลูกค้า (เฉพาะตัวเลข)"""
        return re.sub(r'\D', '', self.partner_id.vat or '')

    def _bill_amount_satang(self):
        """ยอดเงินหน่วยสตางค์ (จำนวนเต็ม) สำหรับบาร์โค้ด"""
        amt = Decimal(str(self.get_billing_amount())).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return str(int((amt * 100).to_integral_value()))

    # ------------------------------------------------------------------
    # Bill Payment: Barcode (มาตรฐานบาร์โค้ดชำระเงินของธนาคารไทย - Code128)
    #   รูปแบบ:  |BillerID \r Ref1 \r Ref2 \r Amount(สตางค์)
    # ------------------------------------------------------------------
    def get_bill_payment_barcode_value(self):
        biller = self.get_comp_code()
        if not biller:
            return ''
        return u"|%s\r%s\r%s\r%s" % (
            biller, self._bill_ref1(), self._bill_ref2(), self._bill_amount_satang())

    def get_bill_payment_barcode_image(self):
        value = self.get_bill_payment_barcode_value()
        if not value:
            return ''
        try:
            img = self.env['ir.actions.report'].barcode(
                'Code128', value, width=560, height=90, humanreadable=0, quiet=1)
            return base64.b64encode(img).decode('ascii')
        except Exception as e:  # noqa: BLE001
            _logger.warning("bill payment barcode error: %s", e)
            return ''

    # ------------------------------------------------------------------
    # Bill Payment: QR (มาตรฐาน EMVCo / Thai QR Bill Payment - PromptPay)
    # ------------------------------------------------------------------
    @staticmethod
    def _emv_tlv(tag, value):
        return '%s%02d%s' % (tag, len(value), value)

    @staticmethod
    def _emv_crc16(payload):
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

    def get_bill_payment_qr_payload(self):
        biller = self.get_comp_code()
        if not biller:
            return ''
        ref1 = self._bill_ref1()
        ref2 = self._bill_ref2()
        amount = '%.2f' % self.get_billing_amount()

        # Tag 30: Bill Payment (merchant account information)
        merchant = self._emv_tlv('00', 'A000000677010112')  # AID Bill Payment
        merchant += self._emv_tlv('01', biller)             # Biller ID / Comp Code
        merchant += self._emv_tlv('02', ref1)               # Reference 1
        if ref2:
            merchant += self._emv_tlv('03', ref2)           # Reference 2

        payload = self._emv_tlv('00', '01')                 # Payload Format Indicator
        payload += self._emv_tlv('01', '12')                # Point of Initiation (12 = dynamic/มียอด)
        payload += self._emv_tlv('30', merchant)            # Bill Payment
        payload += self._emv_tlv('53', '764')               # Currency THB
        payload += self._emv_tlv('54', amount)              # Amount
        payload += self._emv_tlv('58', 'TH')                # Country
        payload += '6304'                                   # CRC tag + length
        payload += self._emv_crc16(payload)
        return payload

    def get_bill_payment_qr_image(self):
        payload = self.get_bill_payment_qr_payload()
        if not payload:
            return ''
        try:
            img = self.env['ir.actions.report'].barcode(
                'QR', payload, width=180, height=180)
            return base64.b64encode(img).decode('ascii')
        except Exception as e:  # noqa: BLE001
            _logger.warning("bill payment QR error: %s", e)
            return ''
