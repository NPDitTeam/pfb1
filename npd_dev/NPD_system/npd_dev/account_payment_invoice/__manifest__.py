{
    'name': 'Account Payment Invoice',
    'version': '14.0.4',
    'summary': 'Account Payment Invoice',
    'description': 'Account Invoice',
    'category': 'account',
    'author': 'Phongsan Boriphan',
    'website': 'www.ashiraplus.co.th',
    "license": "AGPL-3",
    'depends': ['base','account','account_cheque','l10n_th_tax_invoice','withholding_tax_cert_amount'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_payment_invoice_view.xml',
        'views/res_users_views.xml',
        # 'wizard/account_payment_register_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}