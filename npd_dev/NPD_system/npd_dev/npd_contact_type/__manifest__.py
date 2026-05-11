# -*- coding: utf-8 -*-
{
    'name': 'NPD Contact Type - Sale to Invoice',
    'version': '14.0.1.0.0',
    'category': 'Sales',
    'summary': 'ส่งค่า contact_type จาก Sale Order ไปยัง Invoice',
    'description': """
        โมดูลนี้จะส่งค่า field contact_type (การติดต่อของลูกค้า) 
        จาก Sale Order ไปบันทึกที่ Invoice เมื่อกดสร้างใบแจ้งหนี้
    """,
    'author': 'NPD Dev',
    'depends': [
        'sale',
        'account',
        'sale_management',
    ],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
