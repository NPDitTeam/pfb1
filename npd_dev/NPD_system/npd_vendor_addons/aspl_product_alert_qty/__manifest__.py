# -*- coding: utf-8 -*-
#################################################################################
# Author      : Acespritech Solutions Pvt. Ltd. (<www.acespritech.com>)
# Copyright(c): 2012-Present Acespritech Solutions Pvt. Ltd.
# All Rights Reserved.
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################

{
    'name': 'Product Low Stock Notification',
    'version': '1.0',
    'summary': 'Product Low Stock Notification',
    'description': """Product Low Stock Notification""",
    'category': 'general',
    'website': 'http://acespritech.com',
    'author': 'Acespritech Solutions Pvt. Ltd.',
    'price': 20.00,
    'currency': 'EUR',
    'depends': ['base_setup', 'sale_management', 'sale_stock', 'purchase', 'stock', 'stock_account'],
    'images': ['static/description/email_template_configure.png'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_qty_alert.xml',
        'views/product_config_settings.xml',
        'views/alert_qty_wizard.xml',
        'reports/report_wizard_template.xml',
        'reports/report.xml',
        'views/mail_template.xml',
        'views/report_wizard.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
