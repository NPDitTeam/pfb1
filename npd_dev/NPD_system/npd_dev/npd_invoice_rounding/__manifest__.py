# -*- coding: utf-8 -*-
{
    'name': 'NPD Invoice Rounding',
    'version': '14.0.1.0.4',
    'summary': 'ปัดเศษยอดรวมใบแจ้งหนี้อัตโนมัติ',
    'description': """
        โมดูลสำหรับปัดเศษยอดรวมใบแจ้งหนี้
        - ปัดเศษตามหลักคณิตศาสตร์ (>= 0.50 ปัดขึ้น, < 0.50 ปัดลง)
        - สร้าง Rounding Line ใน Journal Entry เพื่อให้ Debit = Credit
        - กดปุ่ม "อัพเดททศนิยม" เพื่อปัดเศษ
    """,
    'author': 'NPD Development',
    'category': 'Accounting',
    'depends': [
        'account',
    ],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
