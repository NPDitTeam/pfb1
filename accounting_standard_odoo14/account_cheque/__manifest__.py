{
    'name': 'Account Cheque',
    'version': '14.0.1',
    'summary': 'Account Cheque',
    'description': 'Account Cheque',
    'category': 'account',
    "author": "Perfect Blending",
    "website": "https://www.perfectblending.com",
    "license": "AGPL-3",
    'depends': ['base','account','payment_method'],
    'data': [
        'security/ir.model.access.csv',
        'security/rule_security.xml',
        'views/account_cheque_view.xml',
        'wizard/date_cheque_done_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}