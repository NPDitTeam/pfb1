# -*- coding: utf-8 -*-
{
    'name': 'NPD Debt Tracking',
    'version': '14.0.1.1.0',
    'summary': 'ติดตามหนี้ลูกค้า',
    'description': """
        ระบบติดตามหนี้ลูกค้า
        - เลือก Sale Order ที่ค้างชำระ
        - แสดงยอดค้างชำระและรายละเอียดลูกค้า
        - กดโทรหาลูกค้าได้
        - บันทึกประวัติการโทร
        - ส่งเมลติดตามหนี้
        - บันทึกประวัติการส่งเมล
    """,
    'author': 'NPD',
    'category': 'Sales',
    'depends': ['sale', 'sale_management', 'account', 'mail', 'pfb_npd_add_date_quatation_order'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/assets.xml',
        'views/debt_tracking_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
