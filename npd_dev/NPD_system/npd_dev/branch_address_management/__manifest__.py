# -*- coding: utf-8 -*-
{
    'name': 'Branch Address Management',
    'version': '14.0.1.0.0',
    'category': 'Sales',
    'summary': 'จัดการที่อยู่ของ Branch',
    'description': """
        โมดูลสำหรับจัดการที่อยู่ของ Branch
        - แสดง popup เพื่อเลือกที่อยู่
        - อัพเดทที่อยู่ไปยัง res.branch
    """,
    'author': 'NPD Dev',
    'website': '',
    'depends': ['sale', 'base','branch'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/branch_address_wizard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
