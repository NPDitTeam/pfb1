# -*- coding: utf-8 -*-
{
    'name': 'NPD Sync Order Date to Rent Start Date',
    'version': '14.0.1.0.0',
    'category': 'Sales',
    'summary': 'ปุ่มอัปเดต SQL ให้วันที่สั่งซื้อ (date_order) เปลี่ยนตามวันที่เริ่มต้นการเช่า (start_rent_date)',
    'description': """
        เพิ่มปุ่มที่ใบสั่งขาย (sale.order) สำหรับสั่งให้ฟิลด์วันที่สั่งซื้อ
        (date_order) อัปเดตตามวันที่เริ่มต้นการเช่า (start_rent_date)
        โดยใช้คำสั่ง SQL UPDATE โดยตรง
    """,
    'author': 'NPD',
    'depends': [
        'sale',
    ],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
