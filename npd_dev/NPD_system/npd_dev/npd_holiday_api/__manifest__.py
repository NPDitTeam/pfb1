# -*- coding: utf-8 -*-
{
    'name': 'NPD Holiday API',
    'version': '14.0.1.0.0',
    'summary': 'REST API + JSON-RPC สำหรับดึงข้อมูลวันหยุดบริษัทจาก payroll.holiday',
    'description': """
        โมดูลนี้ให้ API สำหรับ external app (เช่น HRMS Mobile App)
        เพื่อดึงข้อมูลวันหยุดประจำปีของบริษัทจาก payroll.holiday และ payroll.holiday.line
        - REST API: GET /api/holidays?year=2026
        - JSON-RPC: ผ่าน method get_company_holidays ของ model payroll.holiday
    """,
    'author': 'NPD',
    'category': 'Human Resources',
    'depends': ['base', 'employee_salary'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
