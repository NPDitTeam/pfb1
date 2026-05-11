{
    'name': 'PFB Payment Method Credit Card',
    'version': '14.0.1',
    'summary': 'Account Credit Card',
    'description': 'Account Credit Card',
    'category': 'account',
    'author': 'Thatsawan',
    'website': '',
    "license": "AGPL-3",
    'depends': ['base','account','payment_method','payment_method','account_voucher','account_payment_invoice'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_credit_card_view.xml',
        'views/account_payment_credit_card.xml',
        'wizard/date_credit_card_done_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}