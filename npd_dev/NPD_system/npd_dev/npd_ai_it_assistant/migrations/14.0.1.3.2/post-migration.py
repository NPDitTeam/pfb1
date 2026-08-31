# -*- coding: utf-8 -*-
u"""เปิดสิทธิ์ยกเลิกให้ผู้ใช้ระบบเพิ่ม สำหรับฐานข้อมูลที่ติดตั้งโมดูลไปแล้ว

รอบก่อนเปิดให้แค่ allow_cancel รอบนี้เพิ่ม account_payment_lock_draft_date
ที่ด่านของโมดูล account_payment_invoice ใช้ตอน account.payment.action_draft()
(เหตุผลทั้งหมดอยู่ใน hooks.py)
"""
from odoo.addons.npd_ai_it_assistant.hooks import grant_system_cancel_right


def migrate(cr, version):
    if not version:
        return
    grant_system_cancel_right(cr)
