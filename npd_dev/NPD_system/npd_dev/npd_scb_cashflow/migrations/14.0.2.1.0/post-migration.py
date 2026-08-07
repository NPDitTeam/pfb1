# -*- coding: utf-8 -*-
u"""ตั้งค่าเริ่มต้นของแท็บ Statement_Kbank ให้ฐานข้อมูลที่มีโมดูลอยู่แล้ว

ค่า default ของฟิลด์ใหม่มีผลเฉพาะกับ record ที่สร้างหลังจากนี้
record ตั้งค่า (singleton) ที่มีอยู่แล้วต้องเติมค่าให้เองที่นี่

เฉพาะช่องที่ยังว่างเท่านั้น — ไม่ทับค่าที่ผู้ใช้ตั้งไว้
"""
import logging

_logger = logging.getLogger(__name__)

DEFAULTS = {
    'statement_sheet_kbank': 'Statement_Kbank',
    'statement_range_kbank': 'A2:I',
    'statement_range_ktb': 'A2:O',
}


def migrate(cr, version):
    if not version:
        return

    for column, value in DEFAULTS.items():
        cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = 'npd_scb_cashflow_config' AND column_name = %s
        """, (column,))
        if not cr.fetchone():
            continue
        cr.execute("""
            UPDATE npd_scb_cashflow_config
               SET %s = %%s
             WHERE %s IS NULL OR btrim(%s) = ''
        """ % (column, column, column), (value,))
        if cr.rowcount:
            _logger.info("npd_scb_cashflow: ตั้ง %s = %s ให้ %s รายการ",
                         column, value, cr.rowcount)
