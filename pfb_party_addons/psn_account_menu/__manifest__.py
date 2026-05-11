# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'PFB Odoo 14 Accounting Menu',
    'version': '14.0.1.0',
    'category': 'Accounting',
    'summary': 'Accounting Menu',
    'live_test_url': '',
    'sequence': '8',
    'website': 'https://www.perfectblending.com/',
    'author': 'wattanadev',
    'maintainer': 'wattanadev',
    'license': 'LGPL-3',
    'support': 'info@thaiodoo.com',
    'website': '',
    'depends': [
                'account'

                ],

    'demo': [],
    'data': [
        'views/account.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
    'qweb': [],
}
