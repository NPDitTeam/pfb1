{
    'name': 'PFB Standard : Asset Duplicate Seq',
    'version': '14.0.1',
    'summary': 'asset duplicate seq',
    'description': 'asset duplicate seq',
    'category': 'Asset',
    "author": "Perfect Blending",
    "website": "https://www.perfectblending.com",
    "license": "AGPL-3",
    'depends': ['account_asset_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/asset_duplicate_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
