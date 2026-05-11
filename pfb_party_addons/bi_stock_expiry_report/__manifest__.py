# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
################################################################################

{
    'name' : 'Stock Inventory Ageing Expiry Report in odoo',
    'version' : '14.0.0.0',
	'summary': 'Expiry stock report Stock Aging report aging report  inventory Aging report inventory expiry report product stock expiry report Expiry Report for product Expiry Report for stock product Expiry Report product stock card report Inventory Breakdown report',
    'description': """Stock Expiry Report
    expired stock report expired product report expired product stock report
    Stock Expiry Report in odoo warehouse reports in odoo stock managment in odoo inventory expiry report 

    Expiry stock report Stock Ageing report aging report stock aging report inventory 
    Expiry product report Expiry product stock report Stock Ageing Analysis Report Stock Ageing Report odoo
    warehouse Stock Ageing Analysis Reports Product Expiry Dates Warning Report Lot Expiry Report
    product stock Expiry report batch expiry date Report material expiry date report
    stock product report Aged Stock Analysis blocked inventory Inventory Aging Report expiry inventory
    stock product report expiry stock product report expired for product report expired for stock
    stock product report expiry for product report expiry for stock Product Expiry Dates Warning Report Material Aging Report
    stock  Expiry Report for product Expiry Report for stock product Expiry Report for warehouse Expiry Report for location
    stock expired Report for product expired Report for stock product expired Report for warehouse expired Report for location
    stock expired report product expired report product stock expired  print inventory reports
    download inventory reports print stock reports download stock reports Stock Inventory Aging Report PDF/Excel
    Odoo Stock Inventory Report

   This modules helps to print Inventory Age Report print and print Inventory Breakdown Report
    odoo print Stock Inventory Aging reports print Inventory Aging report print Stock Aging report
    odoo print Stock Inventory age reports print Inventory age report print Stock age report
    odoo stock inventory age report stock age report warehouse aging report
    odoo stock aging report stock inventory aging report
    odoo stock card report product stockcard report product age report product aging reports print
    odoo product stock reports product stock record cards report
    odoo stock bin cards odoo product bin cards
    warehouse product stock aging reports
    odoo Inventory Age Breakdown Report Odoo product stock Break down report Odoo product stock Breakdown reports
    odoo stock Inventory Breakdown report product Stock Inventory Age Breakdown product Inventory stock Age Breakdown
    odoo warehouse Inventory Breakdown Aging report odoo product Average age of inventory increases
    product Inventory age stock report product Inventory Age Report in Odoo & Break down report in Odoo,
    print stock inventory to move product and increase cash flow reports
    print inventory reports stock odoo download inventory reports
    print stock reports odoo download stock reports odoo

    odoo print stock aging report print stock inventory aging report
    odoo print stock card print report product stockcard report print product age report product aging reports download stock reports
    odoo print product stock reports print product stock record cards report print
    odoo print stock bin cards odoo print product stock ageing repots print bin cards reports
    print warehouse product stock aging reports print

    """,
    'category' : 'Warehouse',
    'depends' : ['base','sale_management', 'account','stock','purchase','product_expiry'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/stock_expiry_report_wizard.xml',
        'report/report_stock_expiry_template.xml',
        'report/report.xml',
        'views/stock_report.xml',
        'views/mail_templates.xml',
        'report/report_stock_expiry_template_all.xml',
        'report/report_stock_expiry_template_location.xml',
        'report/report_stock_expiry_template_warehouse.xml'
        ],
    'author': 'BrowseInfo',
    'price': 29,
    'currency': "EUR",
    'website': 'https://www.browseinfo.in',
    "auto_install": False,
    "installable": True,
    "live_test_url": "https://youtu.be/SktAYhgHm1A",
    "images":['static/description/Banner.png'],
    
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

