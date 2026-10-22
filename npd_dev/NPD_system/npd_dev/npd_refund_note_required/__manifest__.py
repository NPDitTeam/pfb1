# -*- coding: utf-8 -*-
{
    'name': 'NPD ใบลดหนี้ บังคับกรอกเงื่อนไขและข้อกำหนด',
    'version': '14.0.1.0.0',
    'summary': 'ใบลดหนี้ลูกค้าต้องกรอกช่อง เงื่อนไขและข้อกำหนด (narration) ก่อนบันทึก/ยืนยัน',
    'description': """
* ฟอร์มใบลดหนี้ลูกค้า (out_refund) ที่ยังเป็นร่าง: ช่องเงื่อนไขและข้อกำหนดเป็นช่องบังคับ
* กดยืนยันแล้วช่องว่าง = แจ้งเตือน ไม่ให้ยืนยัน (เฉพาะเอกสารที่ไม่เคยยืนยันมาก่อน
  ใบเก่าที่ถูกตั้งเป็นร่างแล้วยืนยันซ้ำ เช่นจากเมนูแก้ฐาน/VAT จึงไม่ติด)
    """,
    'category': 'Accounting',
    'author': 'NPD',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
