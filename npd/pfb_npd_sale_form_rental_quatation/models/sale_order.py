import os
import base64

from odoo import models, fields, api, _
from bahttext import bahttext

# แมป ชื่อ database -> ชื่อไฟล์รูป QR code (ตามชื่อบริษัท)
# ใช้ได้ทั้งโฟลเดอร์ qr_code_deposit และ qr_code_rent (ชื่อไฟล์เดียวกัน)
QR_FILE_BY_DB = {
    'TEST_New': 'นภดล เอสกรุ๊ป จำกัด.png',
    'NPD_S_Group_New': 'นภดล เอสกรุ๊ป จำกัด.png',
    'NPD_S_Group_New_V2': 'นภดล เอสกรุ๊ป จำกัด.png',
    'NPD_Bangkok_New': 'นภดล กรุงเทพ จำกัด.png',
    'NPD_Intertrading_New': 'นภดล อินเตอร์เทรดดิ้ง จำกัด.png',
    'NPD_Intertrading_New_NonVat': 'นภดล อินเตอร์เทรดดิ้ง จำกัด.png',
    'NPD_Steeltech_New': 'นภดล สตีลเทค จำกัด.png',
    'NPD_Logistics_New': 'เอ็นพีดี โลจิสติกส์ จำกัด.png',
}

# ค่าขนส่งใช้รูปเดียวเสมอ (บริษัท เอ็นพีดี โลจิสติกส์)
QR_LOGISTICS_FILE = 'เอ็นพีดี โลจิสติกส์ จำกัด.png'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _read_qr_image_b64(self, folder, filename):
        """อ่านไฟล์รูปจาก static/<folder>/<filename> แล้วคืนค่า base64 (str)
        ถ้าไม่มีไฟล์คืนค่าว่าง '' เพื่อให้รายงานไม่ error"""
        if not filename:
            return ''
        # .../models/sale_order.py -> ขึ้นไป 1 ระดับ = root ของโมดูล
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(module_path, 'static', folder, filename)
        try:
            with open(path, 'rb') as f:
                return base64.b64encode(f.read()).decode('ascii')
        except (IOError, OSError):
            return ''

    def get_qr_code_image(self, qr_type):
        """คืนค่า base64 ของรูป QR code ตามประเภท
        qr_type: 'deposit' (ค่าประกัน), 'rent' (ค่าเช่า), 'logistics' (ค่าขนส่ง)
        - deposit/rent: เลือกไฟล์ตามชื่อ database ที่ login
        - logistics: ใช้รูปเดียวเสมอ"""
        if qr_type == 'logistics':
            return self._read_qr_image_b64('qr_code_logistics', QR_LOGISTICS_FILE)
        folder = 'qr_code_deposit' if qr_type == 'deposit' else 'qr_code_rent'
        filename = QR_FILE_BY_DB.get(self.env.cr.dbname)
        return self._read_qr_image_b64(folder, filename)

    def get_qr_company_name(self, qr_type):
        """คืนค่าชื่อบริษัทที่โอนเงิน (แสดงใต้ QR code)
        - logistics: เอ็นพีดี โลจิสติกส์ จำกัด เสมอ
        - deposit/rent: ตามชื่อ database ที่ login
        ดึงจากชื่อไฟล์รูปโดยตัดนามสกุล .png ออก"""
        if qr_type == 'logistics':
            filename = QR_LOGISTICS_FILE
        else:
            filename = QR_FILE_BY_DB.get(self.env.cr.dbname)
        if not filename:
            return ''
        return os.path.splitext(filename)[0]

    # def get_baht_text(self):
    #     calc = sum(self.order_line.mapped('pfb_amount'))
    #     sum_amount = self.amount_total + self.pfb_amount
    #     return bahttext(sum_amount)

    def get_baht_text_rental_quatation(self):
        total_amount = self.amount_total + self.pfb_amount
        if not total_amount:
            return "0 บาท"
        text = bahttext(total_amount)
        satang = round((total_amount - int(total_amount)) * 100)
        if satang == 1:
            text = text.replace('เอ็ดสตางค์', 'หนึ่งสตางค์')
        return text


