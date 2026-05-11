# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Assets Management Odoo',
    'version': '14.0.0.4',
    'category': 'Account',
    'depends': ['account'],
    'summary': 'Apps for Account Assets Management Accounting purchase assets Accounting Assets management Property Assets depreciations Account Assets Community Edition',
    'description': """
Assets management
=================
Manage assets owned by a company or a person.
Keeps track of depreciations, and creates corresponding journal entries.
 Account Assets management
 Accounting Assets management in Odoo 12
 Account Asset in Odoo 12
 manage Account Asset odoo 12
 Assets Management Odoo12
 Purchase Assest manageement
 Assets for Acccouing
 Assets accounnting
 Assets & Finance management
 IT inventory management
 inventory management in Odoo 
 odoo 12 office IT inventory management in odoo 
 odoo12 Asset Management app 
 odoo12 property asset management
 Odoo12 Account Assets management
 Odoo12 Account Asset management
 Odoo12 Assets Account Management
 Odoo12 Asset Account management
 assets odoo12
 assets management odoo12
 assets account odoo12
 assets account management odoo12
 assets account odoo 12
 assets odoo 12
 assets account odoo 12
 assets account management odoo 12
 Odoo 12 Account Assets management
 Odoo 12 Account Asset management
 Odoo 12 Assets Account Management
 Odoo 12 Asset Account management
 
 Account Assets management
 Account Asset management
Asset purchase
Asset account
Accounting purchase assets
Assets management on accounting 

    """,
    'author': 'BrowseInfo',
    'website': 'https://www.browseinfo.in',
    'category': 'Accounting',

    'price': 39,
    'currency': "EUR",
    'data': [
        'security/account_asset_security.xml',
        'security/ir.model.access.csv',
        'wizard/asset_depreciation_confirmation_wizard_views.xml',
        'wizard/asset_modify_views.xml',
        'views/account_asset_views.xml',
        'views/account_invoice_views.xml',
        'views/product_views.xml',
        'report/account_asset_report_views.xml',
        'data/account_asset_data.xml',
    ],
    'qweb': [
        "static/src/xml/account_asset_template.xml",
    ],
    "images":["static/description/Banner.png"],
    'live_test_url':'https://youtu.be/VGgxj_ux9e4',
}
