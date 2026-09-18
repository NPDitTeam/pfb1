# -*- coding: utf-8 -*-
u"""ให้สิทธิ์หัวข้อ "ช่วยปิดงบ" กับผู้ใช้ชุดตั้งต้น สำหรับฐานที่ติดตั้งโมดูลไปแล้ว

post_init_hook ทำงานเฉพาะตอนติดตั้งใหม่ ฐานข้อมูลที่ติดตั้งโมดูลนี้ไปก่อนหน้า
(ทั้ง 5 ฐานบนเซิร์ฟเวอร์) จึงต้องอาศัย migration ตัวนี้ตอนสั่ง -u
รายชื่อผู้ใช้อยู่ที่ CLOSING_HELP_LOGINS ใน hooks.py
"""
from odoo.addons.npd_ai_it_assistant.hooks import grant_closing_help_users


def migrate(cr, version):
    if not version:
        return
    grant_closing_help_users(cr)
