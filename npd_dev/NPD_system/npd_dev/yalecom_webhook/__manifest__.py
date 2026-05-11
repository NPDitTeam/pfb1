# -*- coding: utf-8 -*-
{
    'name': 'Yalecom Webhook Integration',
    'version': '14.0.1.0.0',
    'summary': 'รับข้อมูล Callback จาก Yalecom API',
    'description': """
        โมดูลสำหรับรับข้อมูลจาก Yalecom ผ่าน Webhook/Callback
        
        คุณสมบัติ:
        - รับข้อมูลสายโทรเข้า/ออก (Call Callback)
        - เก็บประวัติการโทร
        - ดาวน์โหลดไฟล์เสียง
        - ตั้งค่า API Key สำหรับความปลอดภัย
        
        Webhook URL: https://your-odoo.com/api/yalecom/callback
    """,
    'author': 'NPD Development',
    'website': 'https://yalecom.co.th/',
    'category': 'Sales/CRM',
    'depends': ['base', 'mail', 'crm'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/yalecom_views.xml',
        'views/yalecom_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
