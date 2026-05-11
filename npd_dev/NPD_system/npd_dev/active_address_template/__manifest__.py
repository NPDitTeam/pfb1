# -*- coding: utf-8 -*-
{
    'name': 'Active Address Template',
    'version': '14.0.1.0.0',
    'category': 'Administration',
    'summary': 'Manage and activate address templates for companies',
    'description': """
        Active Address Template Module
        ===============================
        
        This module allows you to:
        - Create multiple address templates
        - Set one address as active
        - Store complete address information including:
            * Street address
            * City
            * State/Province
            * ZIP/Postal code
            * Country
            * Phone number
            * Email address
        - Switch between different addresses easily
        - Filter and search address templates
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
    ],
    'data': [
        'security/ir_model_access.xml',
        'views/active_address_template_views.xml',
    ],
    'installable': True,
    'application': True,
}
