{
    'name': 'PSN Is a Customer, Is a Vendor',
    'version': '1.0.1',
    'author': 'wattanadev',
    'category': 'Tools',
    'depends': ['base', 'sale_management', 'purchase'],
    'summary': ' ',
    'description': '''
Odoo14 Is a Customer, Is a Vendor
=================================
This module provide two fields <b>Is a Customer, Is a Vendor</b> in to the partner to identify contact is customer/vendor or not. 
In Odoo14 those fields are removed. We have added them back same as like older version.

KEY FEATURES:
-------------
    * Easy To Use.
    * Added Is Customer, Is vendor checkbox Into The Partner Form For Identification.
    * User Can Manually Set/ Unset Customer and Vendor Checkbox.
    * Added Customer Filter In Sale Order.
    * Added Vendor Filter In Purchase Order.
''',
    'data': ['views/res_partner_view.xml'],
    'post_init_hook': 'update_old_partners',
    'images': ['static/description/psn_is_customer_is_vendor_banner.gif'],


    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
}
