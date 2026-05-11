# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    "name" : "Multi Branch for Budget Management-Community Edition",
    "version" : "14.0.0.0",
    "category" : "Accounting",
    'summary': 'Multi Branch budget management multiple branch budget multi branch multiple branch account budget multi unit operation for budget unit budget multiple branch budget operation unit for budget multiple analytic account multi branch analytic accounting branch',
    "description": """
       This odoo app works with community editions and helps user to create and manage budget for multiple branch of single company in odoo community edition, User can create budget, budgetary positions and add branch, Also for analytic account and select specific branch of budgetary positions on same branch of budget also pass this to budget reporting.
    """,
    "author": "BrowseInfo",
    "website" : "https://www.browseinfo.in",
    "price": 39,
    "currency": 'EUR',
    "depends" : ['base', 'branch','bi_account_budget'],
    "data": [
        'security/budget_ir_rule.xml',
        'views/budget_view.xml',
        'views/account_analytic_account.xml',
        'views/account_analytic_line.xml',
        'views/account_move.xml',
        'views/crossovered_budget_lines.xml',
        'views/purchase_order.xml',
        'views/sale_order.xml',
        'views/account_budget_post.xml',
    ],
    "auto_install": False,
    "installable": True,
    "live_test_url":'https://youtu.be/yJSgUOxRJ5w',
    "images":["static/description/Banner.png"],
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
