{
    'name': 'PFB Standard : Asset Stock Receipt',
    'version': '14.0.1',
    'summary': 'Asset Stock Receipt',
    'description': 'Asset Stcok Receipt',
    'category': 'Account',
    'author': 'Phongsan',
    'license': 'LGPL-3',
    'depends': ['account_asset_management','stock', 'pfb_std_asset_free_field', 'purchase'],
    'data': ['views/stock_picking_view.xml',],
    'installable': True,
    'auto_install': False,
}
