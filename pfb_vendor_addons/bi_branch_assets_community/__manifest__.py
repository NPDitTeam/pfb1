# -*- coding: utf-8 -*-
# Part of Browseinfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Multiple Branch(Unit) Operation Setup for Assets Management(Community Edition)',
    'version': '14.0.0.0',
    'category': 'Accounting',
    'sequence': 15,
    'summary': 'Multiple Branch Assets for community multiple unit for assets multi branch assets multi branch multiple unit operation for accounting assets multi branch accounting assets Multiple branch assets depreciations multi branch Assets operating unit for company',
    'description': """

       operating unit for company.
       Multiple Branch Operation Setup for customer
       Unit Operation Setup for Assets Manahement

       Multiple Branch Operation Setup for Account Assets management,
       Unit Operation Setup for helpdesk,
       multiple branch Assets for community,
       multiple branch Account Assets,
       Account Assets multiple branch,
       Account Assets multiple operating unit,
       Account Asset Operating unit,
       Account Assets Operating Unit,
       Asset multiple unit operation,

    """,
    'author': 'BrowseInfo',
    'website': 'https://www.browseinfo.in',
    "price": 20,
    "currency": 'EUR',
    
    'depends': ['base','bi_account_asset', 'branch'],
    'data': [
            'security/branch_asset_ir_rule.xml',
            'views/branch_assets_view.xml',],
    'demo': [],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'live_test_url':'https://youtu.be/XYWG9NW4KyI',
    "images":["static/description/Banner.png"],
}
