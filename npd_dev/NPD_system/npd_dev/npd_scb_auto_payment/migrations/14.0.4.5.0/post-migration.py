# -*- coding: utf-8 -*-
u"""จัดการผลตรวจเก่าที่ค้างอยู่จากตอนที่ยังไม่มีสถานะ "ไม่ใช่สลิปการโอน"

เดิมไฟล์ที่ AI บอกว่าไม่ใช่สลิป (50 ทวิ / ใบกำกับภาษี) ถูกบันทึกเป็น
"อ่านสลิปไม่ได้" ซึ่งลากทั้งใบรับชำระไปเป็น "ไม่สำเร็จ"

ปัญหาคือใบพวกนี้จะไม่หายเอง เพราะ
  1. บรรทัดสลิปที่อ่านแล้วจะไม่ถูกอ่านซ้ำ (จนกว่าจะกด "ตรวจสอบใหม่")
  2. ใบที่ไม่สำเร็จเกิน verify_retry_failed ครั้ง cron จะเลิกตรวจให้แล้ว
     (เจอจริงที่ 9 ครั้ง ขณะที่เพดานคือ 3)

จึงต้องแปลงสถานะให้ตรง แล้วรีเซ็ตตัวนับให้ cron กลับมาตรวจให้ใหม่
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # 1) บรรทัดที่ AI เคยตัดสินว่าไม่ใช่สลิป -> สถานะใหม่ (ไม่ต้องเรียก AI ซ้ำ)
    cr.execute("""
        UPDATE npd_scb_payment_slip
           SET state = 'not_slip'
         WHERE state = 'unreadable'
           AND reason LIKE %s
     RETURNING payment_id
    """, [u'%ไม่ใช่สลิป%'])
    payment_ids = sorted({row[0] for row in cr.fetchall() if row[0]})
    _logger.info(u"SCB: แปลงบรรทัดสลิปเป็น 'ไม่ใช่สลิปการโอน' ใน %s ใบรับชำระ",
                 len(payment_ids))

    # 2) ใบที่ได้รับผลกระทบ + ใบที่ยังมีบรรทัด 'อ่านสลิปไม่ได้' ค้างอยู่
    #    รีเซ็ตตัวนับให้ cron กลับมาตรวจให้ใหม่ด้วยตรรกะที่แก้แล้ว
    cr.execute("""
        UPDATE account_payment p
           SET scb_verify_attempts = 0
         WHERE p.scb_verify_state = 'failed'
           AND (p.id = ANY(%s) OR EXISTS (
                   SELECT 1 FROM npd_scb_payment_slip s
                    WHERE s.payment_id = p.id AND s.state = 'unreadable'))
    """, [payment_ids or [0]])
    _logger.info(u"SCB: รีเซ็ตตัวนับให้ตรวจใหม่ %s ใบ", cr.rowcount)
