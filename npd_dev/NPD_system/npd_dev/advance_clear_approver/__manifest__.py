# -*- coding: utf-8 -*-
{
    'name': 'Advance Clear Approver',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Add approver confirmation feature to Advance Clear',
    'description': """
        This module adds:
        - Checkbox in user settings to mark user as approver
        - Approver confirmation button in Advance Clear (only visible to approvers)
        - Auto-assign current logged in user as approver when confirmed
        - Note field for approver comments
    """,
    'author': 'NPD Dev',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account_advance',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/approver_wizard_views.xml',
        'views/res_users_views.xml',
        'views/account_advance_clear_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
