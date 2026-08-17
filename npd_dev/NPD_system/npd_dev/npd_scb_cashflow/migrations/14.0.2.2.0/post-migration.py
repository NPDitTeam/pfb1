# -*- coding: utf-8 -*-
u"""ล้างรายการเดินบัญชีที่ซ้ำ แล้วสร้างคีย์แถวใหม่ด้วยเวลาที่ย่อรูปแบบแล้ว

ชีตเขียนเวลาของรายการเดียวกันได้สองแบบ ("14:18" กับ "14:18:00") ซึ่งเดิม
ถูกนำไปทำคีย์แถวตรง ๆ รายการเดียวกันจึงถูกเก็บซ้ำเป็นสองแถว ยอดเงินเข้า
งอกขึ้นมาเป็นเท่าตัว (เจอจริงบน NPD_S_Group_New_V2: 180 แถว 1.33 ล้านบาท)

ผลเสียที่ตามมาคือตัวตรวจ "เงินเข้าก้อนเดียวถูกตัดเกิน" จะมองว่ามีเงินเข้า
สองก้อน ทั้งที่จริงมีก้อนเดียว การบันทึกรับชำระซ้ำจึงหลุดรอดไปได้

ลำดับการทำงาน
  1. ย้ายการอ้างอิง (ผลตรวจรายสลิป / ใบรับชำระ) จากแถวซ้ำไปแถวที่เก็บไว้
  2. ลบแถวซ้ำ
  3. สร้าง row_key ใหม่ทุกแถวด้วยสูตรเดียวกับโค้ดปัจจุบัน
     (ข้อ 3 ห้ามข้าม ไม่งั้นการซิงก์ครั้งหน้าจะมองว่าทุกแถวเป็นของใหม่หมด)
"""
import hashlib
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# ย่อเวลาเป็น HH:MM แบบเดียวกับ _time_key() ในโมเดล
TIME_KEY_SQL = """
    lpad(coalesce(nullif(split_part(coalesce(time,''), ':', 1), ''), '0'), 2, '0')
    || ':' ||
    lpad(coalesce(nullif(split_part(coalesce(time,''), ':', 2), ''), '0'), 2, '0')
"""


def migrate(cr, version):
    # ---- 1) หาแถวซ้ำ: เหมือนกันทุกอย่าง ต่างแค่รูปแบบเวลา ----
    cr.execute("""
        CREATE TEMP TABLE scb_dup AS
        SELECT id, min(id) OVER (
                   PARTITION BY source, coalesce(account_no,''), date, %s,
                                coalesce(tr_code,''), coalesce(withdrawal,0),
                                coalesce(deposit,0), coalesce(balance,0)
               ) AS keep_id
          FROM npd_scb_bank_statement
    """ % TIME_KEY_SQL)
    cr.execute("SELECT count(*) FROM scb_dup WHERE id <> keep_id")
    dup_count = cr.fetchone()[0]

    if dup_count:
        # ---- 2) ย้ายการอ้างอิงไปแถวที่เก็บไว้ ก่อนลบ ----
        cr.execute("""
            UPDATE npd_scb_payment_slip s SET statement_id = d.keep_id
              FROM scb_dup d
             WHERE s.statement_id = d.id AND d.id <> d.keep_id
        """)
        moved_slips = cr.rowcount
        cr.execute("""
            UPDATE account_payment p SET scb_statement_id = d.keep_id
              FROM scb_dup d
             WHERE p.scb_statement_id = d.id AND d.id <> d.keep_id
        """)
        moved_payments = cr.rowcount
        cr.execute("""
            DELETE FROM npd_scb_bank_statement
             WHERE id IN (SELECT id FROM scb_dup WHERE id <> keep_id)
        """)
        _logger.info(u"SCB: ลบรายการเดินบัญชีที่ซ้ำ %s แถว "
                     u"(ย้ายผลตรวจรายสลิป %s รายการ, ใบรับชำระ %s ใบ)",
                     dup_count, moved_slips, moved_payments)
    else:
        _logger.info(u"SCB: ไม่พบรายการเดินบัญชีที่ซ้ำ")

    cr.execute("DROP TABLE IF EXISTS scb_dup")

    # ---- 3) สร้าง row_key ใหม่ทุกแถว ----
    env = api.Environment(cr, SUPERUSER_ID, {})
    Model = env['npd.scb.bank.statement']
    cr.execute("""
        SELECT id, coalesce(account_no,''), date, coalesce(time,''),
               coalesce(tr_code,''), coalesce(withdrawal,0), coalesce(deposit,0),
               coalesce(balance,0)
          FROM npd_scb_bank_statement
    """)
    updates = []
    for rid, acc, date, time, tr_code, withdrawal, deposit, balance in cr.fetchall():
        raw = u'|'.join([
            acc,
            date.isoformat() if date else '',
            Model._time_key(time),
            tr_code,
            '%.2f' % float(withdrawal),
            '%.2f' % float(deposit),
            '%.2f' % float(balance),
        ])
        updates.append((hashlib.md5(raw.encode('utf-8')).hexdigest(), rid))

    for key, rid in updates:
        cr.execute("UPDATE npd_scb_bank_statement SET row_key = %s WHERE id = %s",
                   (key, rid))
    _logger.info(u"SCB: สร้างคีย์แถวใหม่ %s แถว", len(updates))
