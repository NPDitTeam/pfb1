# -*- coding: utf-8 -*-
{
    'name': 'Account Voucher User Settings',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Add user settings to control voucher editing',
    'description': """
        Add checkbox in user settings to control editing of Bill Information
        in account voucher.
    """,
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}