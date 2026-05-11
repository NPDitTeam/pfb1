# -*- coding: utf-8 -*-

{
    "name": "Update Stock Quantity",
    'version': '14.0.0.0',
    "author": "Bytelegion",
    "website": "http://www.bytelegions.com",
    'company': 'Bytelegion',
    'depends': ['base', 'sale'],
    'license': 'LGPL-3',
    "category": 'Inventory',
    'sequence': 10,

    "summary": 'This Module is used to hide and show the only required field in Inventory Tree view.',
    "description": """'This Module is used to hide and show the only required field in Inventory Tree view.""",

    'data': [
        'views/inventory.xml',
        'views/service_view.xml',
        'views/update_product.xml',

        # 'security/security.xml',
        'security/ir.model.access.csv',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/banner.gif'], 
    
}
