# -*- coding: utf-8 -*-
{
    'name': 'NPD Analytic Branch',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'summary': 'เพิ่ม field สาขาใน Analytic Account',
    'description': '''
        โมดูลนี้เพิ่ม field branch_id ใน account.analytic.account
        เพื่อเชื่อมโยง Analytic Account กับสาขาโดยตรง
    ''',
    'author': 'NPD',
    'depends': [
        'analytic',
        'branch',
    ],
    'data': [
        'views/account_analytic_account_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
