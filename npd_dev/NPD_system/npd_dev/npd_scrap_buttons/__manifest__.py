# -*- coding: utf-8 -*-
{
    'name': 'NPD Scrap Buttons',
    'version': '14.0.1.0.0',
    'summary': 'Add Reset to Draft and Cancel buttons to Scrap Orders',
    'description': """
        This module adds:
        - Reset to Draft button
        - Cancel button
        to the Scrap Orders form view.
    """,
    'category': 'Inventory',
    'author': 'NPD',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'views/stock_scrap_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
