# -*- coding: utf-8 -*-
{
    'name': 'Custom Fields',
    'version': '14.0.1',
    'category': 'Extra Tools',
    'summary': 'Create Custom Fields Without Any Coding.',
    'description': """
         This module is use for add custom field 
         to form and tree view of any model as per requirement.
     """,
    "author": "Perfect Blending",
    "website": "https://www.perfectblending.com",
    'maintainer': 'zepHyr',
    'depends': [
        'base'
    ],
    'data': [
        'security/custom_fields_groups.xml',
        'security/ir.model.access.csv',
        'data/custom_field_widgets_data.xml',
        'views/custom_fields_views.xml',
        # 'views/custom_base_fields_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
