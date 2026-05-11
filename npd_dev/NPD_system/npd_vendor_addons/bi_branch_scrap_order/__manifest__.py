# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    "name" : "Multi Branch Operations for Scrap Order Odoo App",
    "version" : "14.0.0.1",
    "category" : "Warehouse",
    'summary': 'Multi Branch for scrap order for multi branch scrap order multiple branch scrap order for multi branch warehouse multi branch warehouse unit operation for scrap order multi branch scrap multi branch scrap multiple branch multi unit for scrap order process',
    "description": """
                This odoo app helps user to manage multiple branch for single company, User can also create scrap order for multiple branch and see in tree view also, selected branch will also pass to product moves and journal entry for scrap order. 
           """,
    "author": "BrowseInfo",
    "website" : "https://www.browseinfo.in",
    "price": 40,
    "currency": 'EUR',
    "depends" : ['sale','stock', 'branch'],
    "data": [
        'security/ir_rule.xml',
        'views/stock_scrap.xml',
    ],
    "auto_install": False,
    "installable": True,
	"live_test_url":'https://youtu.be/AL3NMI_JYu4',
	"images":['static/description/Banner.png'],
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
