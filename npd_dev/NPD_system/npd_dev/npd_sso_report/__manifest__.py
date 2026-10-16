# -*- coding: utf-8 -*-
{
    'name': 'NPD รายงานประกันสังคม + สรุปรายได้รายเดือน',
    'version': '14.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'ไฟล์ยื่นประกันสังคม (แยกชีตตามรหัสสาขา สปส.) และรายงานสรุปรายได้ต่อเดือนจากหน้าทำเงินเดือน',
    'description': """
เมนูใต้ "เงินเดือนพนักงาน"
- กำหนดค่ารายงานประกันสังคม: เลขบัญชีนายจ้าง + จับคู่รหัสสาขา สปส. กับสาขาของเรา (รายบริษัท)
- รายงานประกันสังคม: เลือกบริษัท/เดือน ดูตัวอย่างแล้วดาวน์โหลดไฟล์ .xls แบบเดียวกับที่ยื่น สปส.
- รายงานสรุปรายได้ต่อเดือน: เลขผู้เสียภาษี พนักงาน รายได้สุทธิ ประกันสังคม ภาษี
""",
    'author': 'NPD',
    'depends': ['employee_salary'],
    'data': [
        'security/ir.model.access.csv',
        'views/sso_config_views.xml',
        'wizard/sso_report_wizard_views.xml',
        'views/payroll_monthly_summary_views.xml',
        'views/menus.xml',
        'data/sso_config_data.xml',
    ],
    'installable': True,
    'application': False,
}
