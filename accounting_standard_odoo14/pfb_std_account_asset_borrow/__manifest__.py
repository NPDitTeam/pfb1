# -*- coding: utf-8 -*-

{
    'name': 'PFB Standard : Account Asset Borrow',
    "version": "14.0.1",
    'category': 'Account Asset Borrow',
    'description': """Account Asset Borrow""",
    "author": "Thatsawan",
    "website": "https://www.perfectblending.com",
    'summary': 'Asset Borrow Management',
    'depends': ["mail", "account_asset_management", "pfb_std_asset_menu"],
    'images': ['static/description/icon.png'],
    'data': [
        'security/sprogroupasset.xml',
        'security/ir.model.access.csv',
        'data/asset_data.xml',
        'views/asset_borrow_views.xml',
        'views/asset_provide_views.xml',
        'views/asset_views.xml',
        'views/asset_inventory_views.xml',
         'models/wizard/export_view.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'sequence': 105,
    'license': 'AGPL-3',
}
