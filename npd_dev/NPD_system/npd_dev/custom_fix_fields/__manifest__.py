{
    'name': 'Custom Fix Fields',
    'version': '14.0.1.0.0',
    'category': 'Technical',
    'summary': 'Fix missing fields and database issues',
    'description': """
        Custom module to fix missing fields and database schema issues
        - Fixes missing columns in database
        - Extends models with required fields
        - Handles data migration
    """,
    'author': 'NPD',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}