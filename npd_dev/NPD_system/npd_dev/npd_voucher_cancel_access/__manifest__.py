# -*- coding: utf-8 -*-
{
    'name': 'NPD Voucher Cancel Access',
    'version': '14.0.1.0.0',
    'summary': 'ควบคุมสิทธิ์การยกเลิกใบคืนเงินประกันค่าเช่า',
    'description': """
        โมดูลสำหรับควบคุมสิทธิ์การแสดง/ซ่อนปุ่ม Cancel ใน Account Voucher
        - เพิ่มฟิลด์ติ๊กถูกในหน้าตั้งค่าผู้ใช้
        - ถ้าติ๊กถูก = แสดงปุ่ม Cancel
        - ถ้าไม่ติ๊กถูก = ซ่อนปุ่ม Cancel
    """,
    'category': 'Accounting',
    'author': 'NPD',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account_voucher_npd',
    ],
    'data': [
        'security/security_groups.xml',
        'views/res_users_views.xml',
        'views/account_voucher_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
