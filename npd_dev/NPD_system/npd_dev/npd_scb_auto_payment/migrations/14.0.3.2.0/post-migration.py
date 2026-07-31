# -*- coding: utf-8 -*-
u"""ตั้ง "วันที่เริ่มตรวจสอบการโอน" ให้ฐานข้อมูลที่ติดตั้งโมดูลไว้ก่อนแล้ว

post_init_hook ทำงานเฉพาะตอน "ติดตั้งใหม่" ฐานข้อมูลที่มีโมดูลอยู่แล้วจะไม่โดน
จึงต้องตั้งค่าให้ที่นี่ด้วย ไม่งั้นค่าจะว่าง = ไม่จำกัดย้อนหลัง แล้ว cron
จะกวาดใบรับชำระเก่าทั้งฐานข้อมูลมาเรียก AI อ่านสลิปทีละใบจนโควตาหมด

ผู้ใช้แก้วันที่ (หรือล้างให้ว่างเพื่อตรวจย้อนหลังทั้งหมด) ได้เองที่
เมนู ตรวจสอบการโอนเงิน > ตั้งค่า
"""
import logging

_logger = logging.getLogger(__name__)

KEY = 'npd_scb_auto_payment.verify_start_date'


def migrate(cr, version):
    if not version:
        return

    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (KEY,))
    row = cr.fetchone()
    if row and (row[0] or '').strip():
        return  # ผู้ใช้ตั้งไว้แล้ว ไม่ทับ

    # ค่าเริ่มต้น = พรุ่งนี้ -> ตัดขาดจากของเก่า ตรวจเฉพาะใบรับชำระที่บันทึกใหม่
    cr.execute("""
        INSERT INTO ir_config_parameter (key, value, create_uid, write_uid,
                                         create_date, write_date)
             VALUES (%s, to_char(CURRENT_DATE + 1, 'YYYY-MM-DD'), 1, 1, now(), now())
        ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, write_date = now()
    """, (KEY,))
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (KEY,))
    _logger.info(
        "npd_scb_auto_payment: ตั้งวันที่เริ่มตรวจสอบการโอนเป็น %s (พรุ่งนี้) "
        "— ตรวจเฉพาะใบรับชำระใหม่ ไม่ไล่ย้อนหลัง แก้ได้ที่หน้าตั้งค่า",
        (cr.fetchone() or ('?',))[0])
