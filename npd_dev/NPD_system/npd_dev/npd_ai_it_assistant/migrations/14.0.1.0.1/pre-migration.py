# -*- coding: utf-8 -*-
u"""ปลดล็อก noupdate ของ partner บอท เพื่อให้รูปโปรไฟล์ถูกนำไปใช้จริง

ตอนติดตั้งครั้งแรก data/ai_it_bot_data.xml ตั้ง noupdate="1" ไว้ ค่านั้นถูกเก็บลง
คอลัมน์ ir_model_data.noupdate แล้ว "ค้างถาวร" — การแก้ไฟล์ XML เป็น noupdate="0"
ภายหลังไม่ช่วยอะไร เพราะ Odoo ตัดสินใจจากค่าใน DB ไม่ใช่ค่าในไฟล์:

    models.py::_load_records   ->  if not (update and d_noupdate): to_update.append(data)
    ir_model.py::_build_update_xmlids_query
        ON CONFLICT ... DO UPDATE SET (model, res_id, write_date) = (...)
        WHERE NOT ir_model_data.noupdate

สังเกตว่า query ที่ upsert ir_model_data ไม่ได้เขียนคอลัมน์ noupdate เลย
ค่าเดิมจึงไม่มีวันถูกแก้เอง ต่อให้สั่ง -u กี่รอบก็ตาม

สคริปต์นี้เคลียร์ค่านั้นด้วย SQL ก่อนโหลดข้อมูลโมดูล (pre-migration รันก่อน
load_data เสมอ) รอบนี้ระเบียนบอทจึงถูกเขียนทับตามไฟล์ XML — ได้รูปโปรไฟล์มาด้วย
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = 'npd_ai_it_assistant'
BOT_XMLID_NAME = 'partner_ai_it_bot'


def migrate(cr, version):
    if not version:
        # ติดตั้งใหม่ ไม่ต้องทำอะไร ระเบียนถูกสร้างด้วย noupdate=False อยู่แล้ว
        return

    cr.execute("""
        UPDATE ir_model_data
           SET noupdate = false
         WHERE module = %s
           AND name = %s
           AND noupdate = true
    """, (MODULE, BOT_XMLID_NAME))

    if cr.rowcount:
        _logger.info(
            'ตัวช่วย AI-IT: ปลดล็อก noupdate ของ %s.%s แล้ว '
            'ข้อมูลบอท (รวมรูปโปรไฟล์) จะถูกอัปเดตตามไฟล์ในรอบนี้',
            MODULE, BOT_XMLID_NAME,
        )
