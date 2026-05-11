{
    "name": "PFB Standard : Create Cheque",
    "summary": """Create Cheque""",
    "version": "14.0.1",
    "license": "AGPL-3",
    "development_status": "Beta",
    "author": "Thatsawan",
    'website': 'https://www.perfectblending.com/',
    "depends": ["account_cheque"],
    "data": [
        'security/ir.model.access.csv',
        "wizard/account_create_cheque_view.xml",
        "views/account_cheque.xml",
    ],
    "installable": True,
}
