# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ใช้ซ่อนช่องติ๊กภาษีหัก ณ ที่จ่ายบนฟอร์ม เมื่อลูกค้าเป็นบุคคลธรรมดา
    # (attrs บนวิวอ้างฟิลด์ของเรคคอร์ดตัวเองเท่านั้น ใช้ partner_id.company_type ตรง ๆ ไม่ได้)
    partner_company_type = fields.Selection(
        related='partner_id.company_type',
        string='ประเภทลูกค้า',
        readonly=True)

    # ติ๊ก = หักภาษี ณ ที่จ่าย 5% ออกจากยอดใบแจ้งหนี้/ใบวางบิล ลูกค้าจ่ายยอดสุทธิ
    #        และเอกสารจะแสดงบล็อก "ข้อมูลภาษี หัก ณ.ที่จ่าย"
    # ไม่ติ๊ก (ค่าเริ่มต้น) = ยอดเต็ม ไม่หักอะไรออก
    # ใช้ได้เฉพาะลูกค้านิติบุคคล บุคคลธรรมดาจะถูกซ่อนช่องนี้ไป
    # ฟิลด์นี้ถูกอ่านโดยรายงานของโมดูล pfb_npd_sale_form_Billing_sheet
    use_wht_billing_sheet = fields.Boolean(
        string='ใช้ภาษีหัก ณ ที่จ่ายใบแจ้งหนี้/ใบวางบิล หัก 5%',
        default=False,
        help='ถ้าติ๊ก: ใบแจ้งหนี้/ใบวางบิล จะหักภาษี ณ ที่จ่าย 5% ของยอดค่าเช่าก่อนภาษีมูลค่าเพิ่ม '
             '(ไม่รวมค่าประกัน) ออกจากจำนวนเงินทั้งสิ้น จำนวนเงินตัวอักษร และยอดในคิวอาร์ '
             'พร้อมแสดงข้อมูลภาษีหัก ณ ที่จ่ายท้ายเอกสาร\n'
             'ถ้าไม่ติ๊ก: แสดงยอดเต็ม ไม่หักภาษี ณ ที่จ่าย'
    )

    is_reservation_quotation = fields.Boolean(
        string='ใบเสนอราคาแบบจอง',
        default=False,
        help='ทำเครื่องหมายหากเป็นใบเสนอราคาแบบจอง'
    )

    def _prepare_invoice(self):
        """Override เพื่อส่งข้อมูลใบเสนอราคาแบบจองไปยัง Invoice"""
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals['is_from_reservation'] = self.is_reservation_quotation
        return invoice_vals
