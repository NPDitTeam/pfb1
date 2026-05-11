{
    'name': 'ใบเสร็จรับเงิน NPD_Logistics_New',
    'version': '14.0.0.1',
    'summary': 'Module for managing custom features',
    'description': """Module for managing custom features""",
    'author': 'Your Name',
    'depends': ['base', 'payment','account_payment_invoice','account'],
    'data': [
        'report/pfb_npd_payment_form.xml',
        'views/account_payment_view.xml',
    ],
    'installable': True,
    'application': False,
}