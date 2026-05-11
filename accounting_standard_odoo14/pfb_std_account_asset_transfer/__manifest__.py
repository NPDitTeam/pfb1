{
    "name": "PFB Standard : Account Assets Transfer",
    "version": "14.0.1",
    "license": "AGPL-3",
    "depends": ["account","account_asset_management","pfb_std_asset_menu"],
    "excludes": ["account_asset"],
     "author": "Thatsawan",
    "website": "https://www.perfectblending.com",
    "category": "Accounting & Finance",
    "data": [
        # "security/account_asset_security.xml",
         "security/ir.model.access.csv",
        "report/account_asset_transfer_report.xml",
        "views/account_asset_transfer_type.xml",
         "views/account_asset_transfer.xml",
        "views/menuitem.xml",
    ],
}
