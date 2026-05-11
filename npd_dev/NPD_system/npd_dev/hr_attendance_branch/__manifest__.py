{
    'name': 'Employee Attendance by Branch',
    'version': '1.0',
    'summary': 'Check-in/Check-out with Branch Selection',
    'category': 'Human Resources',
    'author': 'Your Company',
    'depends': ['base', 'branch', 'employee_salary'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu.xml',
        'views/manual_time_log_views.xml',
        'views/attendance_views.xml',

    ],
    'installable': True,
    'auto_install': False,
}
