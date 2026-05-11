# -*- coding: utf-8 -*-
{
    'name': 'Add Products in Sale Order by Scanning Barcode',
    'summary': 'Add products in sale order by Scanning Barcode',
    'description': """Add products in sale order by Scanning Barcode.""",

    'author': 'iPredict IT Solutions Pvt. Ltd.',
    'website': 'http://ipredictitsolutions.com',
    "support": "ipredictitsolutions@gmail.com",

    "category": "Sales",
    'version': '14.0.0.1.1',
    "depends": ["sale_management", 'barcodes'],

    'data': [
        'views/sale_order_views.xml'
    ],

    'license': "OPL-1",
    'currency': "EUR",
    'price': 9,

    'installable': True,
    'auto_install': False,

    "images": ['static/description/main.png'],
    'pre_init_hook': 'pre_init_check',
}
