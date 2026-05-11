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
    'name': 'Non Moving Stock Report',
    'version': '14.0.1.0',
    'sequence': 1,
    'category': 'Generic Modules/Warehouse',
    'description':
        """ 
        This Apps add below functionality into odoo 
        
        1.Non Moving Stock Report

Sometimes the goods lying in the warehouse rot or expire because they sell very little. So how we can stop this thing ! This odoo application helps you to export details of Non Moving Stock into excel file. So you can easily know which products have not left the warehouse for month

Export Non Moving Stock as excel report
Export report from : Inventory > Reporting > None Moving Stock Report

Export Non Moving Stock Report
Non Moving Stock Report

        
    """,
    'summary': 'Non Moving Stock Report based on start date and end date, not moving stock , Export Non Moving Stock,Moving Stock Report, warehouse stock, Stock, dead Stock moving, dead stock, none moving stock, dead stock based on dates', 
    'depends': ['sale','stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/non_moving_wizard.xml',
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
    'price':9.0,
    'currency':'EUR',
    #'live_test_url':'https://youtu.be/A5kEBboAh_k',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
