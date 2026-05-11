{
    "name": "PFB Standard : Asset Free Field And Sequences",
    "summary": """Asset Sequences""",
    "version": "14.0.1",
    "license": "AGPL-3",
    "development_status": "Beta",
    "author": "Thatsawan",
    'website': 'https://www.perfectblending.com/',
    "depends": ["account_asset_management", "pfb_asset_qrcode", 'product',
                'purchase',
                ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_asset_free_field_view.xml",
        "views/account_condition_type.xml",
        'views/product.xml',
    ],
    "installable": True,
}
