# -*- coding: utf-8 -*-
{
    'name': 'NPD Rental Status Update',
    'version': '14.0.1.0.0',
    'summary': 'Update rental status with permission control',
    'description': """
        โมดูลสำหรับอัพเดทสถานะ rental_status ในตาราง sale.order
        - ผู้ใช้ทั่วไป: อัพเดทเป็น "ปิดบิล" ได้เฉพาะเมื่อสถานะเป็น "ครบกำหนด" หรือ "เกินกำหนด"
        - ผู้ใช้ที่มีสิทธิ์พิเศษ: สามารถเลือกอัพเดทเป็นสถานะใดก็ได้
    """,
    'author': 'NPD Dev',
    'category': 'Sales',
    'depends': ['sale', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'wizard/update_rental_status_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
