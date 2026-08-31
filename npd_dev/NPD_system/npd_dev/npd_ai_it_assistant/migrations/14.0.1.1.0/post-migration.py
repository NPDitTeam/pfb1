# -*- coding: utf-8 -*-
u"""เปิดสิทธิ์ allow_cancel ให้ผู้ใช้ระบบ สำหรับฐานข้อมูลที่ติดตั้งโมดูลไปแล้ว

post_init_hook ทำงานเฉพาะตอน "ติดตั้งใหม่" เท่านั้น ฐานข้อมูลที่ติดตั้งโมดูลนี้
ไปก่อนหน้าจึงต้องอาศัย migration ตัวนี้ (เหตุผลทั้งหมดอยู่ใน hooks.py)
"""
from odoo.addons.npd_ai_it_assistant.hooks import grant_system_cancel_right


def migrate(cr, version):
    if not version:
        return
    grant_system_cancel_right(cr)
