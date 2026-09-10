# -*- coding: utf-8 -*-
u"""สกัด "ชื่อคู่ค้า" จากรายละเอียดธนาคารใหม่ทุกแถว

ชื่อคู่ค้าถูกสกัดตอนดึงข้อมูลเข้ามาแล้วเก็บไว้ในตาราง การแก้ตัวสกัดจึงมีผล
เฉพาะแถวที่ดึงเข้ามาใหม่ แถวเดิมยังมีชื่อที่ปนขยะอยู่ ต้องสกัดใหม่ให้ทั้งหมด

ที่แก้รอบนี้
  - K-Cash Connect Plus ต่อท้ายรายละเอียดรายการมาในคอลัมน์เดียวกับชื่อ
    "หจก. เอสพีเอ็ม.ไซน++ DIRECT CREDIT Ref 2026090847671862"
    ทุกอย่างหลัง ++ ไม่ใช่ชื่อแล้ว ถ้าไม่ตัดทิ้งจะเทียบกับชื่อลูกค้าไม่ติด
  - เพิ่มคำนำหน้า "รับเงินจาก" (SCB) และ "โอนเข้า" (หักบัญชีอัตโนมัติ)
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Statement = env['npd.scb.bank.statement']

    cr.execute("""
        SELECT id, description, coalesce(counterparty,''), coalesce(counterparty_acc,'')
          FROM npd_scb_bank_statement WHERE description IS NOT NULL AND description <> ''
    """)
    changed = 0
    for row_id, description, old_name, old_acc in cr.fetchall():
        name, acc = Statement._extract_counterparty(description)
        if name == old_name and (acc or '') == old_acc:
            continue
        cr.execute("""UPDATE npd_scb_bank_statement
                         SET counterparty = %s, counterparty_acc = %s WHERE id = %s""",
                   (name or None, acc or None, row_id))
        changed += 1
    _logger.info(u"SCB: สกัดชื่อคู่ค้าใหม่ %s แถว", changed)

    if not changed:
        return

    # ใบที่เคยตรวจไม่ผ่านเพราะเทียบชื่อไม่ติด ต้องได้ตรวจใหม่ด้วยชื่อที่สะอาดแล้ว
    # (ใบที่ไม่สำเร็จจนครบเพดาน cron จะเลิกตรวจให้ ถ้าไม่รีเซ็ตก็ค้างอยู่อย่างนั้น)
    cr.execute("SELECT to_regclass('public.account_payment')")
    if not cr.fetchone()[0]:
        return
    cr.execute("""
        UPDATE account_payment SET scb_verify_attempts = 0
         WHERE scb_verify_state = 'failed' AND coalesce(scb_verify_attempts, 0) > 0
    """)
    _logger.info(u"SCB: รีเซ็ตตัวนับให้ตรวจใหม่ %s ใบ", cr.rowcount)
