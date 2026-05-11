{
    'name': 'Custom Payment Popup',
    'version': '14.0.1.0.0',
    'depends': ['account','account_payment_invoice','account_payment_sequence'],
    'author': 'Your Company',
    'category': 'Accounting',
    'summary': 'Add payment popup button in invoice view',
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_view.xml',
    ],
    'installable': True,
    'application': False,
}
