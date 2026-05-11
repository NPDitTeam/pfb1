# -*- coding: utf-8 -*-

from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)

thai_number = ("ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า")
unit = ("", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน", "ล้าน")

def unit_process(val):
    length = len(val) > 1
    result = ''

    for index, current in enumerate(map(int, val)):
        if current:
            if index:
                result = unit[index] + result

            if length and current == 1 and index == 0:
                result += 'เอ็ด'
            elif index == 1 and current == 2:
                result = 'ยี่' + result
            elif index != 1 or current != 1:
                result = thai_number[current] + result

    return result

def thai_num2text(number):
    s_number = str(number)[::-1]
    n_list = [s_number[i:i + 6].rstrip("0") for i in range(0, len(s_number), 6)]
    result = unit_process(n_list.pop(0))

    for i in n_list:
        result = unit_process(i) + 'ล้าน' + result

    return result

def amount_to_text_thai(amount):
    integer_part, decimal_part = "{:.2f}".format(amount).split(".")
    integer_text = thai_num2text(int(integer_part))
    if int(decimal_part) > 0:
        decimal_text = thai_num2text(int(decimal_part))
        return integer_text + "บาท" + decimal_text + "สตางค์"
    else:
        return integer_text + "บาทถ้วน"

class ReportPurchaseOrder(models.AbstractModel):
    _name = 'report.pfb_npd_po_qweb.report_po'
    _description = 'Report Purchase Order'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('pfb_npd_po_qweb.report_po')
        records = self.env['purchase.order'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,
            'amount_to_text_custom': self.amount_to_text_custom,  # เพิ่มฟังก์ชันนี้ใน context
        }

    @staticmethod
    def amount_to_text_custom(amount):
        # ตรวจสอบจำนวนทศนิยม
        str_amount = "{:.4f}".format(amount)
        integer_part, decimal_part = str_amount.split(".")
        if len(decimal_part) == 4:
            # ตัดให้เหลือ 2 ตำแหน่ง
            amount = round(amount, 2)
        return amount_to_text_thai(amount)
