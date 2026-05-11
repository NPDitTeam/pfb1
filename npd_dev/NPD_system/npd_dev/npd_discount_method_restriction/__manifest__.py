# -*- coding: utf-8 -*-
{
    'name': 'NPD Discount Method Restriction',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Restrict discount method to Percentage only on Account Move',
    'description': """
        This module restricts the Discount Method field on Account Move (Invoice/Bill)
        to only allow 'Percentage' option. If user selects 'Fixed', a warning will be shown.
        
        Reference Module: bi_sale_purchase_discount_with_tax
    """,
    'author': 'NPD Development',
    'depends': [
        'account',
        'bi_sale_purchase_discount_with_tax',
    ],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
