# -*- coding: utf-8 -*-
{
    'name': 'NPD หนังสือรับรองเงินเดือน',
    'version': '14.0.1.0.0',
    'summary': 'ออกหนังสือรับรองเงินเดือนจากข้อมูลพนักงาน เลือกผู้ลงนาม หัวกระดาษตามบริษัท',
    'description': """
เมนู เงินเดือนพนักงาน > หนังสือรับรองเงินเดือน (ผู้ใช้สั่ง 23 ต.ค. 2569)
* ชื่อ-นามสกุล ตำแหน่ง บริษัท เงินเดือน (+ตัวอักษร) วันเริ่มงาน ระยะเวลาทำงาน ดึงจาก employee.salary แก้ได้ก่อนพิมพ์
* ผู้ลงนามและตำแหน่งใต้ชื่อ ตั้งค่าได้ (เริ่มต้น 2 คน)
* หัวกระดาษ/โลโก้ตามบริษัทของพนักงาน ตั้งค่าได้
* เก็บประวัติการออกหนังสือทุกใบ
    """,
    'category': 'Human Resources',
    'author': 'NPD',
    'license': 'LGPL-3',
    'depends': ['employee_salary', 'mail', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/cert_data.xml',
        'views/salary_certificate_views.xml',
        'reports/salary_certificate_report.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
