# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Analytic Accounts Budgets Management Odoo',
    'category': 'Accounting',
    'version':'14.0.0.0',
    'summary': 'Apps for Account Budget Management Budget Analytic account Budget management Accounting Budget financial budget financial accounting budget planning Account budget Community Edition',
    'description': """
This module allows accountants to manage analytic and crossovered budgets.
==========================================================================

Once the Budgets are defined (in Invoicing/Budgets/Budgets), the Project Managers
can set the planned amount on each Analytic Account.
 budget management in odoo
 Analytic Accounts budget 
 Analytic Accounts budgeting
 Accounting budget Management
 account budgeting in Odoo
 budget planning
 
 Accounting Analytic budget planning
 Accounting Analytic budget in 
The accountant has the possibility to see the total of amount planned for each
Budget in order to ensure the total planned is not greater/lower than what he
planned for this Budget. Each list of record can also be switched to a graphical
view of it.

Three reports are available:
analytic account project budget management
project analytic account management
analytic account plan with budget management
purchase budget management
puchase budget with analytic account
----------------------------
    1. The first is available from a list of Budgets. It gives the spreading, for
       these Budgets, of the Analytic Accounts.

    2. The second is a summary of the previous one, it only gives the spreading,
       for the selected Budgets, of the Analytic Accounts.

    3. The last one is available from the Analytic Chart of Accounts. It gives
       the spreading, for the selected Analytic Accounts of Budgets.
       budget planning
       financial accounting budget planning
       accounting financial planning
       account budget
       accounts budgets
       financial budget
       odoo12 budget management
       account budget odoo12
       odoo12 account budget management
       odoo12 budget analytic account
       odoo 12 analytic account budget management
       odoo12 analytic account budgett management
       odoo 12 account budget
       account budget management for odoo12
       account budget for odoo12
       account budget odoo12
       account budget odoo 12
       budget account odoo12
       budget account odoo 12
       account budget management odoo 12
""",
    'author': 'BrowseInfo',
    'website': 'https://www.browseinfo.in',
    'depends': ['account', 'base'],
    "price": 29,
    "currency": 'EUR',
    'data': [
        'security/ir.model.access.csv',
        'security/account_budget_security.xml',
        'views/account_analytic_account_views.xml',
        'views/account_budget_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'demo': ['data/account_budget_demo.xml'],
    "images":['static/description/Banner.png'],
    'live_test_url':'https://youtu.be/Zn2G60nEKpQ',

}
