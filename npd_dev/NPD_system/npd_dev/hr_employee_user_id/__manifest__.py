# -*- coding: utf-8 -*-
{
    'name': 'HR Employee User ID',
    'version': '14.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Add User ID field to Employee',
    'description': """
        This module adds a User ID field to the Employee form.
    """,
    'author': 'NPD',
    'depends': ['hr'],
    'data': [
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
