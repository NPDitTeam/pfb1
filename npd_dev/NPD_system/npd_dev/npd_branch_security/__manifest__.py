# -*- coding: utf-8 -*-
{
    'name': 'NPD Branch Security',
    'version': '14.0.1.0.0',
    'summary': 'Control Create/Edit/Delete permissions for Branch',
    'description': """
        โมดูลควบคุมสิทธิ์การเพิ่ม/แก้ไข/ลบ ข้อมูลสาขา
        - เพิ่มแท็บสิทธิ์สาขาในหน้าตั้งค่าผู้ใช้
        - ค่าเริ่มต้นไม่อนุญาต (ไม่ติ๊ก)
    """,
    'author': 'NPD Dev',
    'category': 'Administration',
    'depends': ['base', 'branch'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
