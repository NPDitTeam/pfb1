# -*- coding: utf-8 -*-
"""แถวที่มีอยู่ก่อนเพิ่มฟิลด์ is_manual ล้วนมาจากการดึงข้อมูล ไม่ใช่รายการที่สร้างเอง

is_manual ตั้ง default เป็น True เพื่อให้รายการที่กดปุ่ม "สร้าง" ถูกตีเป็นของที่
พนักงานสร้างเองอัตโนมัติ แต่ตอนเพิ่มคอลัมน์ Odoo จะเติมค่า default ให้แถวเดิมทุกแถวด้วย
ถ้าไม่ล้างตรงนี้ แถวเก่าจะรอดจากการลบตอนกดดึงข้อมูลใหม่ แล้วซ้ำกับแถวที่ดึงเข้ามาใหม่
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("UPDATE baankheaw_debt_payment SET is_manual = false")
