{
    'name': 'Custom Cash Payment',
    'version': '14.0.1.0.0',
    'summary': 'ชำระเงินสด',
    'category': 'Accounting',
    'author': 'Your Company',
    'depends': ['account','account_payment_invoice','mail'],
    'data': [
    'security/ir.model.access.csv',
    'views/cash_payment_views.xml',
    'data/cash_payment_sequence.xml',
    'views/menu.xml',
    ],

    'installable': True,
    'application': False,
}
