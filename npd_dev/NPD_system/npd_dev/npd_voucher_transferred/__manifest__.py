# -*- coding: utf-8 -*-
{
    'name': 'NPD Voucher Transfer Status',
    'version': '14.0.1.0.0',
    'summary': 'เพิ่มปุ่ม "โอนแล้ว" บน Account Voucher พร้อมระบบสิทธิ์ผู้ใช้',
    'description': """
        - เพิ่มปุ่ม "โอนแล้ว" บน Account Voucher (การรับ/การขาย)
        - เพิ่ม state ใหม่ "transferred" (โอนแล้ว) พร้อมแถบสถานะสีเขียว
        - ควบคุมสิทธิ์การมองเห็นปุ่มผ่าน checkbox ที่หน้าตั้งค่า User
        - บันทึกวันที่โอน + ผู้ทำรายการโอน
    """,
    'category': 'Accounting',
    'author': 'NPD Dev',
    'depends': [
        'base',
        'account_voucher'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/account_voucher_views.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
