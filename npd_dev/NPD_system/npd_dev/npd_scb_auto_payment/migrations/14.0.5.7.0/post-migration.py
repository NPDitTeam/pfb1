# -*- coding: utf-8 -*-
u"""ปล่อยเงินก้อนที่ใบรับชำระ "ที่ยกเลิก/กลับเป็นร่างไปแล้ว" ยังจับค้างไว้

โค้ดเดิมไม่ปล่อยผลจับคู่ของสลิปตอนยกเลิกใบรับชำระ ใบที่ยกเลิกแล้วจึงยังถูกนับว่า
"ใช้เงินก้อนนี้อยู่" ใบจริงที่ทำใหม่แทนจะตก "ตัดเกิน" ทุกครั้งที่กดตรวจ
(ตอนสำรวจ 2026-09-28: Intertrading 23 ใบ, Bangkok 1 ใบ, S_Group 0 ใบ)

ปล่อยเฉพาะผลจับคู่ (ไม่แตะใบรับชำระ/รายการบัญชี) แล้วให้ใบที่ใช้เงินก้อนเดียวกัน
กลับเป็น "รอตรวจสอบ" ให้ cron ตรวจใหม่
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['npd.scb.payment.slip'].search([('state', '=', 'matched')])
    stale = lines.mapped('payment_id').filtered(lambda p: p.state != 'posted')
    if stale:
        stale._scb_release_on_cancel()
    _logger.info("npd_scb_auto_payment: ปล่อยเงินก้อนจากใบรับชำระที่ไม่ได้ลงบันทึก %s ใบ: %s",
                 len(stale), ', '.join(stale.mapped('name'))[:2000])
