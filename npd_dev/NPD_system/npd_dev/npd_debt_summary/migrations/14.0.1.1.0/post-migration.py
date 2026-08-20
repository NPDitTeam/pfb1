# -*- coding: utf-8 -*-
"""เปลี่ยนรูปแบบเลขที่เอกสารจาก DEBT-2026-00273 เป็น NPS.N 0001/2569

ir.sequence ตัวเดิมถูกประกาศไว้แบบ noupdate="1" การ upgrade โมดูลเฉย ๆ
จึงไม่แก้ค่าให้ ต้องมาเขียนทับตรงนี้:
  prefix  DEBT-%(year)s- -> ว่าง (คำนำหน้าไปประกอบใน python ตาม DB)
  padding 5 -> 4
  เปิด use_date_range แล้วล้างรอบเดิมทิ้ง เลขจะเริ่มนับใหม่ที่ 0001

เอกสารเก่าที่ออกเลขไปแล้วยังเป็นรูปแบบ DEBT-xxxxx เหมือนเดิม
ถ้าต้องการไล่เลขใหม่ทั้งระบบให้เรียก
    env['npd.debt.summary'].action_renumber_documents()
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    seq = env['ir.sequence'].search([('code', '=', 'npd.debt.summary')])
    if not seq:
        _logger.warning('npd_debt_summary: ไม่พบ ir.sequence code npd.debt.summary')
        return
    for record in seq:
        if record.date_range_ids:
            record.date_range_ids.unlink()
        record.write({
            'prefix': '',
            'padding': 4,
            'use_date_range': True,
            'number_next_actual': 1,
        })
    _logger.info('npd_debt_summary: ตั้งเลขรันใหม่เป็น 4 หลัก เริ่มที่ 0001 แล้ว')
