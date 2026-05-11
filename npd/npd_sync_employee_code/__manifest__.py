# -*- coding: utf-8 -*-
{
    'name': 'Sync Employee Code to Users',
    'version': '14.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'อัพเดทรหัสพนักงานจาก Employee Salary ไปยัง res.users ใน DB ปลายทาง',
    'description': """
        อัพเดทรหัสพนักงาน (employee_code) จากตาราง employee.salary
        ไปยัง res.users ใน DB ปลายทางผ่าน JSON-RPC API
        - อัพเดทรายคน
        - อัพเดททั้งหมด
        - อัพเดทตามสาขา
    """,
    'author': 'NPD',
    'depends': ['employee_salary'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/sync_employee_code_wizard_views.xml',
        'views/employee_salary_sync_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
