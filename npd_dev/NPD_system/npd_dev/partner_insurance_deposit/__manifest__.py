# -*- coding: utf-8 -*-
# __manifest__.py
# ไฟล์ manifest สำหรับกำหนดข้อมูลโมดูล Odoo

{
    'name': 'Partner Insurance Deposit',
    'version': '14.0.1.0.0',
    'category': 'Sales',
    'summary': 'เพิ่มฟิลด์ค่าประกันสะสมและประเภทลูกค้าในข้อมูลคู่ค้า',
    'description': """
        โมดูลนี้เพิ่มฟิลด์ในหน้าข้อมูลคู่ค้า (res.partner):
        
        1. ค่าประกันสะสม (Accumulated Insurance Deposit)
           - ต่อจากฟิลด์ Tax Branch
           - คำนวณจาก account.payment
           - กรอง journal "สมุดรายวันรับชำระค่าประกัน"
           - กรอง state = posted
        
        2. ประเภทลูกค้า (Customer Status)
           - ใต้ฟิลด์ Priority
           - ดึงจาก crm.lead ล่าสุด
           - ลูกค้าเก่า / ลูกค้าใหม่
    """,
    'author': 'NPD',
    'license': 'LGPL-3',
    
    # depends: โมดูลที่ต้องติดตั้งก่อน
    # - base: โมดูลพื้นฐาน (res.partner)
    # - account: โมดูลบัญชี (account.payment, account.journal)
    # - crm: โมดูล CRM (crm.lead)
    # - partner_priority: โมดูล priority (priority_id field)
    'depends': ['base', 'account', 'crm', 'partner_priority'],
    
    # data: ไฟล์ XML ที่ต้องโหลด
    'data': [
        'views/res_partner_views.xml',
    ],
    
    'installable': True,
    'auto_install': False,
    'application': False,
}
