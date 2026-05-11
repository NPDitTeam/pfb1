# -*- coding: utf-8 -*-
{
    'name': 'Account Voucher Line Sales Contact',
    'version': '14.0.1.0.1',
    'summary': 'Add Sales Contact field to Voucher Lines',
    'description': """
        เพิ่มฟิลด์ Sales ที่ติดต่อ ใน Voucher Lines
        - แสดงเฉพาะ User ที่อยู่ในแผนก Sales
        - สามารถแก้ไขได้แม้ state = posted ผ่านปุ่ม "แก้ไข Sales ที่ติดต่อ"
    """,
    'author': 'NPD Dev',
    'category': 'Accounting',
    'depends': ['account_voucher', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/wizard_edit_sales_contact_views.xml',
        'views/account_voucher_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
