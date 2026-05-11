{
    'name': 'Withholding Tax Source Document',
    'version': '14.0.1',
    'summary': 'Withholding Tax Source Document',
    'description': 'Withholding Tax Source Document',
     'category': 'account',
    "author": "Perfect Blending",
    "website": "https://www.perfectblending.com",
    "license": "AGPL-3",
    'depends': ['l10n_th_withholding_tax_cert','l10n_th_withholding_tax_report'],
    "data": [
        "views/withholding_tax_cert_views.xml",
        "report/report_withholding_tax_qweb.xml"
    ],
    'installable': True,
    'auto_install': False,
}