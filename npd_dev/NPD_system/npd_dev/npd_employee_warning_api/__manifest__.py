# -*- coding: utf-8 -*-
{
    'name': 'NPD Employee Warning API',
    'version': '1.0',
    'summary': 'API สำหรับแอปมือถือดึงข้อมูลใบเตือนพนักงาน',
    'description': """
        เพิ่ม method ให้ employee.warning และ controller สำหรับดาวน์โหลดไฟล์แนบ
        เพื่อให้ Flutter app (NPD HRMS) เรียกใช้งานได้
    """,
    'category': 'Human Resources',
    'author': 'NPD',
    'depends': ['base', 'web', 'employee_salary'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
