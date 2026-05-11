# -*- coding: utf-8 -*-
{
    'name': 'API ขนส่ง',
    'version': '14.0.1.0.0',
    'category': 'API',
    'summary': 'API สำหรับดึงข้อมูล Sale Order และข้อมูลการขนส่ง',
    'description': """
API สำหรับดึงข้อมูล Sale Order และข้อมูลการขนส่ง
=================================================

ฟีเจอร์หลัก:
    * ดึงข้อมูล Sale Order พร้อมรายละเอียดการจัดส่ง
    * ดึงข้อมูลสินค้าในใบสั่งขาย
    * รองรับการ Authentication ด้วย Odoo Session
    * รองรับการ Filter และ Pagination
    * ดึงข้อมูลจุดรับ-ส่ง, ระยะทาง, ค่าขนส่ง
    * ดึงข้อมูลพนักงานขับรถและป้ายทะเบียน

การใช้งาน:
    1. Authenticate ที่ /web/session/authenticate
    2. ใช้ session_id ที่ได้เรียก API
    3. เรียก /api/sale_orders เพื่อดึงข้อมูล

ดูเพิ่มเติมที่ README.md
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'sale',
        'hr',
        'fleet',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}