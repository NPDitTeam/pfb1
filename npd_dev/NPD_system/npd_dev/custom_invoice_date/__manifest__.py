# -*- coding: utf-8 -*-
{
    'name': 'Custom Invoice Date Management',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'summary': 'จัดการวันที่ Invoice และใบเสนอราคาแบบจอง',
    'description': """
        โมดูลสำหรับจัดการ:
        - แก้ไขวันที่ Invoice Date
        - จัดการใบเสนอราคาแบบจอง
        - ควบคุมการแสดงปุ่มยืนยัน Invoice
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'account',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}