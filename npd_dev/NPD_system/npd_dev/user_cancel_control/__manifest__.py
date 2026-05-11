# -*- coding: utf-8 -*-
{
    'name': 'ควบคุมการยกเลิกผู้ใช้',
    'version': '14.0.1.0.0',
    'category': 'บัญชี',
    'summary': 'ควบคุมสิทธิ์การยกเลิกสำหรับการชำระเงิน บันทึก และใบสั่งขาย',
    'description': 'โมดูลนี้ช่วยให้คุณสามารถจำกัดหรืออนุญาตการยกเลิกตามการตั้งค่าผู้ใช้',
    'author': 'NPD System',
    'website': 'https://github.com/npd-system',
    'depends': ['base', 'account', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
