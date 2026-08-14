# -*- coding: utf-8 -*-
u"""เลิกข้ามสลิปจ่ายบิล (REF) — ชีตมีรายการแยกรายคนพร้อมชื่อผู้โอนแล้ว

เดิม statement ฝั่ง SCB มีแต่แถวสรุปยอดรวมรายวันของบิลเพย์เมนต์
(channel BPAY เวลา 22:59 รายละเอียด "รับชำระค่าสินค้าและบริการ CrossBank")
ซึ่งไม่มีชื่อผู้โอน จึงเทียบกับสลิปไม่ได้ ระบบเลยข้ามสลิปที่มี REF ในเลขอ้างอิง

ตอนนี้ชีตเพิ่มรายการแยกรายคนแล้ว (channel CBBP มีชื่อผู้โอนครบทุกแถว)
จึงต้องปลดสลิปที่เคยถูกข้ามให้กลับมาตรวจ

ไม่เรียก AI ซ้ำ — ค่าที่อ่านจากสลิปถูกเก็บไว้ในบรรทัดผลตรวจอยู่แล้ว
แค่เปลี่ยนสถานะกลับเป็น "รอตรวจสอบ" ระบบจะเอาไปจับคู่ใหม่เอง
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # เคลียร์ค่าที่เคยบันทึกไว้ ให้กลับไปใช้ค่าเริ่มต้นใหม่ (เว้นว่าง = ไม่ข้าม)
    cr.execute("""
        DELETE FROM ir_config_parameter
         WHERE key = 'npd_scb_auto_payment.verify_skip_slip_keywords'
           AND value ILIKE '%REF%'
    """)
    if cr.rowcount:
        _logger.info(u"SCB: ล้างค่า verify_skip_slip_keywords ที่ตั้งเป็น REF ไว้")

    # บรรทัดสลิปที่ถูกข้ามเพราะเป็นการจ่ายบิล -> กลับมารอตรวจ
    cr.execute("""
        UPDATE npd_scb_payment_slip
           SET state = 'to_check', reason = NULL, statement_id = NULL
         WHERE state = 'skipped'
     RETURNING payment_id
    """)
    payment_ids = sorted({row[0] for row in cr.fetchall() if row[0]})
    _logger.info(u"SCB: ปลดสลิปจ่ายบิลกลับมาตรวจ %s บรรทัด (%s ใบรับชำระ)",
                 len(payment_ids), len(payment_ids))

    if not payment_ids:
        return

    # ใบที่เคยสรุปว่า "ไม่ต้องตรวจสอบ" เพราะสลิปถูกข้ามหมด ต้องกลับมาเข้าคิว
    # (ใบที่ข้ามเพราะสมุดรายวัน เช่น "ลดหนี้" ไม่มีบรรทัดสลิป จึงไม่โดนกระทบ)
    cr.execute("""
        UPDATE account_payment
           SET scb_verify_state = 'to_check',
               scb_verify_summary = NULL,
               scb_verify_reason = NULL,
               scb_verify_attempts = 0,
               scb_statement_id = NULL
         WHERE id = ANY(%s)
           AND scb_verify_state IN ('skipped', 'failed')
    """, [payment_ids])
    _logger.info(u"SCB: ตั้งใบรับชำระกลับเป็น 'รอตรวจสอบ' %s ใบ", cr.rowcount)
