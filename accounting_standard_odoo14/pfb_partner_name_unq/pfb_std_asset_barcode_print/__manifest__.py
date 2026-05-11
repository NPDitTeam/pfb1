
{
    "name": "PFB Standard : Asset Barcode Print",
    "summary": """Asset Barcode Print""",
    "version": "14.0.1",
    "license": "AGPL-3",
    "author": "Thatsawan",
    'website': 'https://www.perfectblending.com/',
    "depends": ["account_asset_management"],
    "data": [
        "data/paper_format.xml",
        "views/report_views.xml",
        "reports/report_asset_barcode_print.xml",
    ],
    "installable": True,
}
