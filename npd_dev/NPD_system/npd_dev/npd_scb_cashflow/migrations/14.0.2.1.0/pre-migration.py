# -*- coding: utf-8 -*-
u"""ลบ unique constraint เก่าที่ค้างอยู่บนตาราง npd_scb_cashflow

โมเดลรุ่นแรกใช้ ``unique(key)`` ต่อมาเปลี่ยนเป็น ``unique(source, key)``
เพราะคีย์เดียวกันเกิดขึ้นได้ในหลายธนาคาร (เช่น 0208937774_15/07/2026 มีทั้ง
ฝั่ง SCB และ Kbank) แต่ constraint ตัวเก่าไม่ถูกลบออกจากฐานข้อมูล ทำให้ sync พังด้วย

    duplicate key value violates unique constraint "npd_scb_cashflow_key_uniq"

สคริปต์นี้ลบ unique constraint ทุกตัวบนตารางที่ "ไม่ใช่ตัวที่โมเดลประกาศไว้ตอนนี้"
(ตัวที่ถูกต้อง Odoo จะสร้างให้เองตอนโหลดโมดูล) — เขียนแบบกวาดทั้งตาราง
เพื่อกันกรณีมี constraint เก่าชื่ออื่นค้างอยู่ด้วย
"""
import logging

_logger = logging.getLogger(__name__)

TABLE = 'npd_scb_cashflow'
KEEP = 'npd_scb_cashflow_key_source_uniq'   # unique(source, key) — ตัวที่ใช้อยู่


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT c.conname
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
         WHERE t.relname = %s AND c.contype = 'u' AND c.conname != %s
    """, (TABLE, KEEP))
    stale = [row[0] for row in cr.fetchall()]
    if not stale:
        _logger.info("npd_scb_cashflow: ไม่มี unique constraint เก่าค้างอยู่")
        return

    for name in stale:
        cr.execute('ALTER TABLE "%s" DROP CONSTRAINT IF EXISTS "%s"' % (TABLE, name))
        cr.execute("DELETE FROM ir_model_constraint WHERE name = %s", (name,))
        _logger.info("npd_scb_cashflow: ลบ unique constraint เก่า %s เรียบร้อย "
                     "(ใช้ %s แทน)", name, KEEP)
