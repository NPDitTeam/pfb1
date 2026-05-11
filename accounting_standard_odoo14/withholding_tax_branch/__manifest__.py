{
    'name': 'Withholding Tax Branch',
    'version': '14.0.1',
    'summary': 'Withholding Tax Branch',
    'description': 'Withholding Tax Branch',
     'category': 'account',
    "author": "Perfect Blending",
    "website": "https://www.perfectblending.com",
    "license": "AGPL-3",
    'depends': ['l10n_th_withholding_tax_cert','branch','account_payment_invoice'],
    'data': [
        'views/withholding_tax_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}