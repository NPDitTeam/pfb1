# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################
{
    'name': 'Stock Inventory Aging Report PDF/Excel',
    'version': '14.0.1.2',
    'sequence': 1,
    'category': 'Warehouse',
    'summary': 'odoo Apps will print Stock Aging Report by Company, Warehouse, Location, Product Category, and Product | stock expiry report | inventory expiry report | inventory aging report | Stock Aging Report | Inventory Age Report & Break Down Report | Stock Aging Excel Report',
    'description': """

         odoo Apps will print Stock Aging Report by Compnay, Warehoouse, Location, Product Category and Product.

Stock Inventory Aging Report PDF/Excel
Odoo Stock Inventory Aging Report PDF/Excel
Stock inventory againg report
Oddo stock againg report
Print stock inventory againg report
Odoo print stock againg report
Non moving product report
Odoo non moving report
Print non moving product report
Odoo print non moving product report
Non moving inventory 
Odoo non moving inventory
Non moving inventory report
Odoo non moving inventory report
Inventory age report
Odoo inventory age report
Inventory break down report
Odoo inventory break down report
Inventory Age Report & Break Down Report
Inventory Age Report and Break Down Report
Odoo Inventory Age Report and Break Down Report

Odoo  Inventory Age Report & Break Down Report
Print inventory age report
Odoo print inventory age report
Stock ageing report
Odoo stock ageing report
Stock Ageing Excel Report
Odoo Stock Ageing Excel Report
Stock Aging Report by Company
Odoo Stock Aging Report by Company
   Odoo inventory report 

odoo Apps will print Stock Aging Report by Company, Warehouse, Location, Product Category, and Product | stock expiry report | inventory expiry report | inventory aging report | Stock Aging Report | Inventory Age Report & Break Down Report | Stock Aging Excel Report

    """,
    'author': 'DevIntelle Consulting Service Pvt.Ltd', 
    'website': 'http://www.devintellecs.com',
    'depends': ['purchase','stock','account','sale_stock',],
    'data': [
        'security/ir.model.access.csv',
        'report/inventory_ageing_template.xml',
        'report/report_mennu.xml',
        'wizard/inventory_wizard_view.xml',
        
    ],
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'price':29.0,
    'currency':'EUR', 
    'live_test_url':'https://youtu.be/Sg7NnM_Bz7E', 
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
