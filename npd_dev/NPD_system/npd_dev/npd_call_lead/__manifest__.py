# -*- coding: utf-8 -*-
{
    'name': 'NPD Call Lead',
    'version': '14.0.1.1.0',
    'summary': 'โทรติดตาม Lead ลูกค้า',
    'description': """
        ระบบโทรติดตาม Lead ลูกค้า
        - เลือก Lead ที่ต้องการติดตาม
        - แสดงข้อมูลลูกค้าและรายละเอียด Lead
        - กดโทรหาลูกค้าได้
        - บันทึกประวัติการโทร
        - ส่งเมลติดตาม Lead
        - บันทึกประวัติการส่งเมล
    """,
    'author': 'NPD',
    'category': 'Sales/CRM',
    'depends': ['crm', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/call_lead_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
