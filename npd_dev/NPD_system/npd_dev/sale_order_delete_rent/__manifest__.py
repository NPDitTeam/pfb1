# -*- coding: utf-8 -*-
{
    'name': 'Sale Order Delete Rent',
    'version': '14.0.1.0.0',
    'category': 'Sales',
    'summary': 'Delete Rent Sale Orders with related Invoices and Pickings',
    'description': """
        Module for deleting Rent type Sale Orders along with:
        - Related Invoices (cancel and delete)
        - Related Stock Pickings (cancel and delete)
        - The Sale Order itself (cancel and delete)
    """,
    'author': 'NPD Development',
    'website': '',
    'depends': ['sale', 'stock', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/delete_rent_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
