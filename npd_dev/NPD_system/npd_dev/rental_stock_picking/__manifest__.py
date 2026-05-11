# -*- coding: utf-8 -*-
{
    'name': 'Rental Stock Picking Extension',
    'version': '14.0.1.0.0',
    'category': 'Inventory',
    'summary': 'เพิ่มฟิลด์วันที่เช่าและแก้ไข Force Date',
    'description': """
        - เพิ่มฟิลด์วันที่เริ่มต้น/สิ้นสุดการเช่า
        - กำหนดสิทธิ์แก้ไข Force Date
        - เพิ่มสิทธิ์ผู้ใช้สำหรับแก้ไข
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['stock', 'base'],
    'data': [
        'security/rental_security.xml',
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}