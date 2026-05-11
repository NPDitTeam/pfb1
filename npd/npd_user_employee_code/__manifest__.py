# -*- coding: utf-8 -*-
{
    'name': 'User Employee Code',
    'version': '14.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Add Employee Code field to Users form',
    'description': """
        เพิ่มฟิลด์รหัสพนักงาน (Employee Code) ในหน้าผู้ใช้งาน (res.users)
    """,
    'author': 'NPD',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
