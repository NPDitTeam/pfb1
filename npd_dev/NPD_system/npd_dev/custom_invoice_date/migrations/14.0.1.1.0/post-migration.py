# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """ความหมายของ use_wht_billing_sheet ถูกกลับด้าน

    รุ่นแรก: ติ๊ก = แสดงข้อมูลภาษีหัก ณ ที่จ่าย (ยอดเต็ม)  ค่าเริ่มต้นติ๊กถูก
    รุ่นนี้:  ติ๊ก = หักภาษี ณ ที่จ่าย 5% ออกจากยอด        ค่าเริ่มต้นไม่ติ๊ก

    ใบสั่งขายเดิมถูกเซ็ต True จากค่าเริ่มต้นรุ่นแรก ไม่ใช่ผู้ใช้ตั้งใจติ๊ก
    ถ้าปล่อยไว้ ใบเดิมทุกใบจะกลายเป็นหัก 5% ออกจากยอดทันที จึงต้องล้างเป็นไม่ติ๊ก
    ยอดเงินของใบเดิมจึงเท่าเดิมทุกใบ
    """
    if not version:
        return
    cr.execute("""
        UPDATE sale_order
           SET use_wht_billing_sheet = false
         WHERE use_wht_billing_sheet IS DISTINCT FROM false
    """)
    _logger.info("custom_invoice_date: reset use_wht_billing_sheet on %s sale orders", cr.rowcount)
