# -*- coding: utf-8 -*-
{
    'name': 'NPD Debt Tracking Payment Integration',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'summary': 'เชื่อมต่อการรับชำระกับการติดตามหนี้',
    'description': """
        โมดูลนี้เชื่อมต่อระหว่าง account.payment กับ npd.debt.tracking
        - เมื่อยืนยันการรับชำระ จะอัปเดตยอดชำระใน npd.debt.tracking
        - เมื่อ reset to draft จะเคลียร์ยอดชำระใน npd.debt.tracking
    """,
    'author': 'NPD',
    'depends': [
        'account_payment_invoice',
        'npd_debt_tracking',
    ],
    'data': [
        'views/npd_debt_tracking_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
