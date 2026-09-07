# -*- coding: utf-8 -*-
import re
import base64
import logging
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models
from bahttext import bahttext

_logger = logging.getLogger(__name__)

# หมายเหตุการตั้งชื่อเมธอด:
# โมดูลใบวางบิลอื่น (เช่น pfb_npd_sale_form_Billing_sheet_rent) ก็ inherit sale.order
# เหมือนกัน Odoo รวมทุกโมดูลเป็นคลาสเดียว เมธอดชื่อซ้ำจะทับกันโดยไม่มีคำเตือน
# เมธอดที่รายงานของโมดูลนี้เรียกใช้จึงลงท้ายด้วย _billing_sheet ทั้งหมด


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ------------------------------------------------------------------
    # ยอดเงิน
    # ------------------------------------------------------------------
    def get_grand_total_billing_sheet(self):
        """จำนวนเงินทั้งสิ้น ยอดเดียวที่ใช้ทั้งเอกสาร (ตัวเลขท้ายเอกสาร ตัวอักษร และคิวอาร์)

           - มี deposit_ref = เก็บค่าประกันไปแล้ว จึงไม่บวกค่าประกันซ้ำ
           - ไม่ติ๊ก 'ใช้ภาษีหัก ณ ที่จ่ายใบแจ้งหนี้/ใบวางบิล หัก 5%' (ค่าเริ่มต้น) = ยอดเต็ม
           - ติ๊ก = หักภาษี ณ ที่จ่าย 5% ออกจากยอดให้เลย ลูกค้าจ่ายยอดสุทธิ
             และแสดงบล็อกข้อมูลภาษีหัก ณ ที่จ่ายท้ายเอกสาร"""
        total = Decimal(str(self.amount_total if self.deposit_ref
                            else self.pfb_amount + self.amount_total))
        if self.deduct_wht_billing_sheet():
            total -= Decimal(str(self.get_wht_amount_billing_sheet()))
        return float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    # ------------------------------------------------------------------
    # ภาษีหัก ณ ที่จ่าย
    # ------------------------------------------------------------------
    def get_wht_base_billing_sheet(self):
        """ฐานคำนวณภาษีหัก ณ ที่จ่าย = ยอดค่าเช่าก่อนภาษีมูลค่าเพิ่มเท่านั้น
           ค่าประกันอยู่ในฟิลด์ pfb_amount แยกต่างหาก ไม่ได้รวมใน amount_untaxed
           จึงไม่ถูกนำมาคิดภาษีหัก ณ ที่จ่าย"""
        return self.amount_untaxed

    def get_wht_amount_billing_sheet(self):
        """ภาษีหัก ณ ที่จ่าย 5% ปัดแบบ round-half-up (เช่น 353.025 -> 353.03)"""
        base = Decimal(str(self.get_wht_base_billing_sheet()))
        wht = (base * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return float(wht)

    def get_wht_amount(self):
        # คงชื่อเดิมไว้เผื่อมีที่อื่นเรียกใช้
        return self.get_wht_amount_billing_sheet()

    def wht_applies_billing_sheet(self):
        """เอกสารนี้เกี่ยวข้องกับภาษีหัก ณ ที่จ่ายหรือไม่ — คิดเฉพาะลูกค้านิติบุคคล
           ลูกค้าบุคคลธรรมดาไม่มีการหัก ณ ที่จ่าย จึงไม่หักยอดออกและไม่แสดงบล็อกภาษี
           (ช่องติ๊กบนใบสั่งขายก็ถูกซ่อนไปสำหรับลูกค้าบุคคลธรรมดา)

           ใช้เป็นเงื่อนไขแสดงบล็อก 'ข้อมูลภาษี หัก ณ.ที่จ่าย' ท้ายเอกสารด้วย
           แสดงทั้งกรณีติ๊กและไม่ติ๊ก ต่างกันแค่ยอดถูกหักออกไปแล้วหรือยัง"""
        return self.partner_id.company_type == 'company'

    def deduct_wht_billing_sheet(self):
        """ติ๊ก 'ใช้ภาษีหัก ณ ที่จ่ายใบแจ้งหนี้/ใบวางบิล หัก 5%' = หัก 5% ออกจากยอด

           ฟิลด์ use_wht_billing_sheet นิยามอยู่ในโมดูล custom_invoice_date
           (กลุ่ม 'ข้อมูลการจอง' บนใบสั่งขาย) ซึ่งบางฐานข้อมูลไม่ได้ติดตั้ง
           ถ้าไม่มีฟิลด์ ให้ถือว่าไม่ติ๊ก = ยอดเต็ม ไม่หักอะไรออก เหมือนพฤติกรรมเดิม"""
        return self.wht_applies_billing_sheet() and bool(
            getattr(self, 'use_wht_billing_sheet', False))

    # ------------------------------------------------------------------
    # QR พร้อมเพย์ (มาตรฐาน EMVCo / Thai QR Payment)
    # ------------------------------------------------------------------
    @staticmethod
    def _promptpay_tlv(tag, value):
        return '%s%02d%s' % (tag, len(value), value)

    @staticmethod
    def _promptpay_crc16(payload):
        """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)"""
        crc = 0xFFFF
        for ch in payload.encode('utf-8'):
            crc ^= ch << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
                crc &= 0xFFFF
        return '%04X' % crc

    def _promptpay_account_billing_sheet(self):
        """คืน (sub-tag, ค่า) ของเลขพร้อมเพย์บริษัท โดยดูชนิดจากจำนวนหลัก
           15 หลัก = e-Wallet ID
           13 หลัก = เลขประจำตัวผู้เสียภาษี / บัตรประชาชน
           9-10 หลัก = เบอร์มือถือ แปลงเป็นรูปแบบ 0066 + 9 หลักท้าย"""
        digits = re.sub(r'\D', '', self.company_id.promptpay_id or '')
        if len(digits) == 15:
            return '03', digits
        if len(digits) == 13:
            return '02', digits
        if len(digits) in (9, 10):
            return '01', '0066' + digits[-9:]
        return '', ''

    def get_promptpay_qr_payload_billing_sheet(self):
        """สร้าง payload คิวอาร์พร้อมเพย์ ระบุยอด = จำนวนเงินทั้งสิ้น"""
        tag, account = self._promptpay_account_billing_sheet()
        if not account:
            return ''
        amount = '%.2f' % self.get_grand_total_billing_sheet()

        merchant = self._promptpay_tlv('00', 'A000000677010111')   # AID พร้อมเพย์
        merchant += self._promptpay_tlv(tag, account)

        payload = self._promptpay_tlv('00', '01')     # Payload Format Indicator
        payload += self._promptpay_tlv('01', '12')    # 12 = dynamic (ระบุยอดเงินมาแล้ว)
        payload += self._promptpay_tlv('29', merchant)
        payload += self._promptpay_tlv('53', '764')   # สกุลเงิน THB
        payload += self._promptpay_tlv('54', amount)  # จำนวนเงิน
        payload += self._promptpay_tlv('58', 'TH')    # ประเทศ
        payload += '6304'                             # tag CRC + ความยาว
        payload += self._promptpay_crc16(payload)
        return payload

    def get_promptpay_qr_image_billing_sheet(self):
        """รูปคิวอาร์เป็น base64 ถ้าบริษัทยังไม่ได้ตั้งเลขพร้อมเพย์จะคืนค่าว่าง"""
        payload = self.get_promptpay_qr_payload_billing_sheet()
        if not payload:
            return ''
        try:
            img = self.env['ir.actions.report'].barcode(
                'QR', payload, width=220, height=220)
            return base64.b64encode(img).decode('ascii')
        except Exception as e:  # noqa: BLE001
            _logger.warning("promptpay QR error on %s: %s", self.name, e)
            return ''

    # ------------------------------------------------------------------
    # อื่น ๆ
    # ------------------------------------------------------------------
    def get_date_baht_text(self):
        return bahttext(self.commitment_date)

    def get_rent_daily(self):
        number = 0
        for line in self.order_line:
            number += line.price_unit * line.product_uom_qty
        return number

    def get_total_baht_text_sheet(self):
        return bahttext(self.get_grand_total_billing_sheet())
