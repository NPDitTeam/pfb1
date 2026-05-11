{
    'name': 'Asset IT',
    'version': '14.0.1.0.0',
    'category': 'Human Resources/Employees',
    'summary': 'Asset IT',
    'author': 'INKERP',
    'website': 'https://www.inkerp.com/',
    'depends': ['hr', 'mail'],
    
    'data': [
        'data/ir_sequence.xml',
        'views/asset_category_view.xml',
        'views/asset_detail_view.xml',
        'views/asset_location_view.xml',
        'views/asset_move_view.xml',
        'security/ir.model.access.csv',
    ],
    
    'images': ['static/description/oi_account_asset.png'],
    'license': "OPL-1",
    'installable': True,
    'application': True,
    'auto_install': False,
}
