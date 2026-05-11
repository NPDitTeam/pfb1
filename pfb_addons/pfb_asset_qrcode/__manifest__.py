{
    'name': 'PFB Standard : Account Asset QRcode',
    'version': '14.0.0.1',
    'summary': 'Account Asset QRcode',
    'description': 'Account Asset QRcode',
    'category': 'base',
    "author": "Perfect Blending",
    "website": "https://www.perfectblending.com",
    "license": "AGPL-3",
    'depends': ['account_asset_management'],
    "external_dependencies": {"python": ["qrcode"]},
    'data': [
        'views/asset_view.xml',
        'data/paper_format.xml',
        'reports/report_asset_barcode_print.xml',
        'views/report_views.xml'
    ],
    'installable': True,
    'auto_install': False,
}
