# -*- coding: utf-8 -*-
# Copyright 2020 CorTex IT Solutions Ltd. (<https://cortexsolutions.net/>)
# License OPL-1

{
    'name': "Multi Modules/Apps Uninstall",

    'summary': """
        This module enable you to uninstall multi module with single click.
        """,
    'description': """
modules
apps
module
odoo modules uninstall
odoo uninstall multi modules
odoo multi uninstall
odoo multi module uninstall
modules uninstall
module uninstall
modules multi uninstall
multi uninstall
apps multi uninstall
uninstall multi modules
uninstall multi apps
multi modules uninstall
multi apps uninstall
uninstall modules
uninstall apps
modules mass uninstall
mass modules uninstall
apps mass uninstall
bulk uninstall
modules bulk uninstall
apps bulk uninstall
    """,

    'author': 'CorTex IT Solutions Ltd.',
    'website': 'https://cortexsolutions.net',
    'license': 'OPL-1',
    'currency': 'EUR',
    'price': 8,
    'support': 'support@cortexsolutions.net',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Extra Tools',
    'version': '1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base'],
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'wizard/uninstall_multi_module_views.xml'
    ],
    'images': ['static/description/main_screenshot.png'],
    "installable": True
}
