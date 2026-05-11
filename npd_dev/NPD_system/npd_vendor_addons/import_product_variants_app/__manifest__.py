# -*- coding: utf-8 -*-

{
    'name': 'Import Products and Product Variant From Excel/CSV File',
    "author": "Edge Technologies",
    'version': '14.0.1.0',
    'live_test_url': "https://youtu.be/uug0yNRQ99Q",
    "images":['static/description/main_screenshot.png'],
    'summary':'Import product variant from excel import product from excel product import from csv import product images import product data import product attributes import variants with attributes import product template import products from csv odoo import product',
    'description': """
        This module helps easily import product variant (image, price, quantity, stock etc) from csv or excel.
    """,
    "license" : "OPL-1",
    'depends': ['sale_management','stock'],
    'data': [
        'security/import_product_variant.xml',
        'security/import_custom_fields.xml',
        'security/ir.model.access.csv',
        'views/import_product_variant_view.xml', 
    ],
    'installable': True,
    'auto_install': False,
    'price': 20,
    'currency': "EUR",
    'category': 'Sales',
}
