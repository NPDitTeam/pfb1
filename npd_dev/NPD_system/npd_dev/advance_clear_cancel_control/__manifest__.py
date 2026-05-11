# -*- coding: utf-8 -*-
{
    'name': 'ควบคุมการยกเลิก Advance Clear',
    'version': '14.0.1.0.0',
    'category': 'บัญชี',
    'summary': 'ควบคุมสิทธิ์การยกเลิก Advance Clear ตามการตั้งค่าผู้ใช้',
    'description': 'โมดูลนี้ช่วยให้คุณสามารถจำกัดหรืออนุญาตการกดปุ่ม Cancel ในหน้า Advance Clear ตามสิทธิ์ของแต่ละ User',
    'author': 'NPD System',
    'website': 'https://github.com/npd-system',
    'depends': ['base', 'account_advance'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/account_advance_clear_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
