# -*- coding: utf-8 -*-
{
    'name': 'NPD Debt Summary (รวมหนี้ลูกค้า)',
    'version': '14.0.1.13.0',
    'summary': 'สรุปหนี้ลูกค้า - สแกนลูกค้าที่มีใบแจ้งหนี้ค้างชำระอัตโนมัติ',
    'description': """
        รวมหนี้ลูกค้า (Customer Debt Summary)
        - กดที่เมนู "รวมหนี้ลูกค้า" ระบบจะสแกนลูกค้าที่มีใบแจ้งหนี้ค้างชำระโดยอัตโนมัติ
        - แสดงลูกค้าที่เข้าเงื่อนไข โดยกรุ๊ปตามชื่อลูกค้า
        - แต่ละลูกค้าแสดง 4 แท็บ: ใบแจ้งหนี้ค้างชำระ / ค่าปรับหาย / ค่าปรับชำรุด / ค่า Tax
        - ปุ่มอัพเดทเพื่อดึงข้อมูลใหม่
        (ต่อยอดจากโมดูล npd_debt_tracking โดยตัดส่วนโทร/ส่งเมล/หมายเหตุออก)
    """,
    'author': 'NPD',
    'category': 'Sales',
    'depends': ['sale', 'sale_management', 'account',
                'pfb_npd_add_date_quatation_order', 'npd_debt_tracking_qweb'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/debt_summary_views.xml',
        'views/debt_collection_status_views.xml',
        'report/debt_summary_reports.xml',
        'report/debt_collection_letter.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
