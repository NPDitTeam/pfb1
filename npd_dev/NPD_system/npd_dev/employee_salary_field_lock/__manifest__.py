# -*- coding: utf-8 -*-
{
    'name': 'Employee Salary Field Lock',
    'version': '1.0',
    'summary': 'ล็อคการแก้ไขข้อมูลพนักงาน (employee.salary) ตามผู้ใช้ที่ถูกตั้งค่า',
    'description': """
เพิ่มตัวเลือก (ติ๊กถูก) ในหน้าตั้งค่าผู้ใช้ (Settings > Users)
เมื่อติ๊กถูกให้ผู้ใช้คนนั้น จะไม่สามารถแก้ไขข้อมูลในฟอร์มพนักงาน (employee.salary)
ได้ทั้งหมด "ยกเว้น" สาขา (branch_id) และตำแหน่ง (position_id) ที่ยังแก้ไขได้

การล็อคทำงาน 2 ชั้น:
- ชั้น UI: override fields_view_get ทำให้ทุกฟิลด์ในฟอร์มเป็น readonly
  (ยกเว้นสาขา/ตำแหน่ง) ครอบคลุมทุกฟิลด์รวมถึงฟิลด์ที่โมดูลอื่นเพิ่มเข้ามา
- ชั้น ORM: override write() บล็อกการเขียนฟิลด์การเงิน (ค่าจ้าง/เงินเพิ่ม/
  ประกันสังคม/ภาษี) ที่เปลี่ยนค่าจริง
""",
    'category': 'Human Resources',
    'author': 'NPD',
    'depends': ['employee_salary'],
    'data': [
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
