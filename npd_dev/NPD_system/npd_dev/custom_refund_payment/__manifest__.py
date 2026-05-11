{
    'name': 'Custom Refund Payment',
    'version': '14.0.1.0.0',
    'summary': 'โอนคืนเงินลูกค้า',
    'category': 'Accounting',
    'author': 'Your Company',
    'depends': ['account','account_payment_invoice','mail'],
    'data': [
    'security/ir.model.access.csv',
    'views/refund_payment_views.xml',
    'views/res_users_views.xml',
    'data/refund_payment_sequence.xml',
    'views/menu.xml',
    ],

    'installable': True,
    'application': False,
}
