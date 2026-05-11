{
    'name': 'Account Billing Advance',
    'version': '14.0.1',
    'summary': 'Account Bill Advance',
    'description': 'Account Bill Advance',
    'category': 'account',
    'author': 'Phongsan Boriphan',
    'website': 'www.ashiraplus.co.th',
    "license": "AGPL-3",
    'depends': ['payment_method','account_billing','account_payment_invoice'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_billing_view.xml',
        'wizard/create_bill_payment_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}