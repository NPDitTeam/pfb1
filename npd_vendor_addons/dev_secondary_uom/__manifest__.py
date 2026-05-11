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
    'name': 'Product Secondary UOM/Qty in Sale, Purchase, Invoice',
    'version': '14.0.1.0',
    'sequence': 1,
    'category': 'Sales',
    'description':
        """ 
This Apps add below functionality into odoo 
        
        1.This module helps you to secondary uom in sale,purchase,Inventory and invoice
Product Stock Secondary UOM QTY
Odoo Product Stock Secondary UOM QTY
Manage Product Stock Secondary UOM QTY
Odoo manage Product Stock Secondary UOM QTY
Product stock secondary qty 
Odoo product stock secondary qty 
Manage product stock secondary qty 
Odoo manage product stock secondary qty 
Odoo app will help to show Product stock qty in Secondary UOM As example : Dozen & units, kilogram and grams etc
Add Product stock qty in Secondary UOM on Product Screen
Oddo Add Product stock qty in Secondary UOM on Product Screen
Enable multiple UoM options 
Odoo enable multiple UoM Options 
Secondary UOM Conversations 
Odoo secondary UOM Conversations 
Manage UOM Conversation 
Odoo manage UOM Conversations 
Manage multiple UoM options 
Odoo manage multiple UoM Option 
Secondary UOM in sales
Secondary UOM in purchase
Secondary UOM in Inventory 
Secondary UOM in invoice
Product Secondary UOM/Qty in Sale, Purchase, Invoice
Odoo Product Secondary UOM/Qty in Sale, Purchase, Invoice
Odoo app will helps to add secondary uom and quantity in Sale, Purchase, Inventory and Invoices.
Add Secondary UOM and Quantity in sale,purchase, inventory and invoices
Odoo Add Secondary UOM and Quantity in sale,purchase, inventory and invoices
Easy to Calculate Secondary Quantity from pivot view
Odoo Easy to Calculate Secondary Quantity from pivot view
Manage product secondary UOM 
Odoo manage product secondary UOM 
Manage product secondary qty in sale 
Odoo manage product secondary qty in sale 
Manage product secondary qty in purchase 
Odoo manage product secondary qty in purchase 
Manage product secondary qty in invoice
Odoo manage product secondary qty in invoice 
        
    """,
    'summary': 'Odoo app will helps to add secondary uom and quantity in Sale, Purchase, Inventory and Invoices | Secondary UOM  | secondary Qty | secondary Unit of measure, Secondary UOM/Qty,Secondary Quantity,secondary UOM', 
    'depends': ['sale_management','purchase','sale_stock','account'],
    'data': [
        'security/security.xml',
        'views/product_template_view.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/account_invoice_views.xml',
        'views/stock_move_views.xml',
    ],
    'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    
    # author and support Details =============#
    'author': 'DevIntelle Consulting Service Pvt.Ltd',
    'website': 'http://www.devintellecs.com',    
    'maintainer': 'DevIntelle Consulting Service Pvt.Ltd', 
    'support': 'devintelle@gmail.com',
    'price':15.0,
    'currency':'EUR',
    #'live_test_url':'https://youtu.be/A5kEBboAh_k',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
