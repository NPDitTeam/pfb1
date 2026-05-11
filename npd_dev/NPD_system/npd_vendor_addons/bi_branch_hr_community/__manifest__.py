# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    "name" : "Multi Branch for Human Resource - Community Edition",
    "version" : "14.0.0.0",
    "category" : "Human Resource",
    'summary': 'Multiple Branch Management HR Multi Branch HR Employee app Multiple Unit operation for human resource multi branch HR operation multi branch hr Department branch Payslip Reports for single company Multi Branch employee multi branch for hr multiple branch',
    "description": """
       This odoo app helps user to create multiple branch to manage human resource, user can create multiple branch for single company set to users and employees. branch will automatically selected on records or can select branch manually for job application, employee contract, department, attendance, expenses, expense report. User can also manage payroll in community edition with multiple branch create salary rule, salary structure and create payslip for employee and also can print payslip report.
    """,
    "author": "BrowseInfo",
    "website" : "https://www.browseinfo.in",
    "price": 40,
    "currency": 'EUR',
    "depends" : ['base', 'branch','bi_hr_payroll_account', 'hr_expense', 'hr_attendance', 'hr_recruitment'],
    "data": [
        'security/hr_ir_rule.xml',
        'views/hr_department.xml',
        'views/hr_employee.xml',
        'views/hr_contract.xml',
        'views/hr_payslip.xml',
        'views/hr_expense.xml',
        'views/hr_expense_sheet.xml',
        'views/hr_attendance.xml',
        'views/hr_applicant.xml',
        'report/hr_payslip_details_view.xml',
        ],
    "auto_install": False,
    "installable": True,
    "live_test_url":'https://youtu.be/5Tgvm6P-M2U',
    "images":["static/description/Banner.png"],
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
