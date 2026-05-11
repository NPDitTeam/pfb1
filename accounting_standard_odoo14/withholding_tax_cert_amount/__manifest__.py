{
    'name': 'Withholding Tax Cert Amount',
    'version': '14.0.1',
    'summary': 'Withholding Tax Cert Amount',
    'description': 'Withholding Tax Cert Amount',
    'category': 'account',
    'author': 'Phongsan Boriphan',
    'website': 'www.ashiraplus.co.th',
    "license": "AGPL-3",
    'depends': ['account','account_config','l10n_th_withholding_tax','l10n_th_withholding_tax_cert'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/withholding_tax_cert_view.xml',
        'views/withholding_tax_type_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}