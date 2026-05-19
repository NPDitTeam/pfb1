# -*- coding: utf-8 -*-
{
    'name': 'NPD Sync Order Date to Rent Start Date',
    'version': '14.0.1.1.0',
    'category': 'Sales',
    'summary': 'ปุ่มอัปเดต SQL ให้วันที่สั่งซื้อ (date_order) รวมถึงวันที่ใบแจ้งหนี้/วันที่กำหนดจ่าย เปลี่ยนตามวันที่เริ่มต้นการเช่า (start_rent_date)',
    'description': """
        เพิ่มปุ่มที่ใบสั่งขาย (sale.order) สำหรับสั่งให้:
        - วันที่สั่งซื้อ (date_order) อัปเดตตามวันที่เริ่มต้นการเช่า
          (start_rent_date) โดยคงเวลาเดิมไว้
        - วันที่ใบแจ้งหนี้ (invoice_date) และวันที่กำหนดจ่าย
          (invoice_date_due) ของใบแจ้งหนี้ที่ผูกกับใบสั่งขาย ให้เป็น
          วันเดียวกับวันที่สั่งซื้อ เฉพาะใบแจ้งหนี้สถานะ "ฉบับร่าง"
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
