# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Multi Branch for Pricelists Odoo App',
    'version': '14.0.0.0',
    'category': 'Sales',
    'summary': 'Multi Branch for pricelist multi branch sales pricelist multiple branch pricelists for multi branch sales pricelist multi branch pricelist unit operation for vendor pricelist multi branch sale pricelist multi branch pricelist multiple branch pricelists',
    'description': """
    
       Multi Branch/Unit on Pricelists,
       Multiple Branch for Single Company in odoo,
       Allow Multiple Branch in odoo,
       Branch on Pricelist in odoo,
       Added Branch on Multiple Pricelist in odoo,
       Specific Branch for User in odoo,

    """,
    'author': 'BrowseInfo',
    "price": 40,
    "currency": 'EUR',
    'website': 'https://www.browseinfo.in',
    'depends': ['branch','product'],
    'data': [
        'views/product_pricelist_views.xml',
    ],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'live_test_url':'https://youtu.be/otdROl0tCec',
    "images":['static/description/Banner.png'],
}
