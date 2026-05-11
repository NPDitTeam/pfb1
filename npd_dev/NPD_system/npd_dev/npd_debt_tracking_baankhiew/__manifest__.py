# -*- coding: utf-8 -*-
{
    'name': 'NPD Debt Tracking Baankhiew',
    'version': '14.0.1.3.2',
    'summary': 'ติดตามหนี้บ้านเขียว (ค่าเช่า/ค่าปรับชำรุด) พร้อมรายงาน',
    'description': """
        ระบบติดตามหนี้ลูกค้าบ้านเขียว
        - รองรับ 2 ประเภทหนี้: ค่าเช่า และ ค่าปรับชำรุด
        - เลือก Sale Order ที่ค้างชำระ
        - แสดงยอดค้างชำระและรายละเอียดลูกค้า
        - กดโทรหาลูกค้าได้
        - บันทึกประวัติการโทร
        - ส่งเมลติดตามหนี้
        - บันทึกประวัติการส่งเมล
        - รายงานติดตามหนี้ทั้งหมด (SQL View)
    """,
    'author': 'NPD',
    'category': 'Sales',
    'depends': ['sale', 'sale_management', 'account', 'mail', 'pfb_npd_add_date_quatation_order'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/assets.xml',
        'views/debt_tracking_baankhiew_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': '_post_init_hook',
}
