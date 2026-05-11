# -*- coding: utf-8 -*-
{
    'name': 'Rental Diff Charge',
    'version': '14.0.1.0.0',
    'summary': 'เพิ่มฟิลด์เก็บค่าเช่าส่วนต่างใน Stock Picking',
    'description': """
        โมดูลสำหรับเพิ่มฟิลด์เก็บค่าเช่าส่วนต่างใน Stock Picking
        - ฟิลด์ collect_rental_diff (Boolean) สำหรับระบุว่าต้องเก็บค่าเช่าส่วนต่างหรือไม่
        - ค่าเริ่มต้น: ไม่ติ๊กถูก (False)
    """,
    'category': 'Inventory/Inventory',
    'author': 'NPD Development',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'rental_stock_picking',
    ],
    'data': [
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
