# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Payment Method',
    'version': '14.0.1',
    'category': 'Account',
    'description': """
            Payment Method
    """,
     "author": "Perfect Blending",
    "website": "https://www.perfectblending.com",
    "license": "AGPL-3",
    'depends': [
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/payment_method_security.xml',
        'views/payment_method_view.xml',
    ],
}
