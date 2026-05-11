# -*- coding: utf-8 -*-
{
    'name': 'NPD Tax Lock for Rental',
    'version': '14.0.1.0.0',
    'category': 'Sales',
    'summary': 'Lock tax selection for sale/rental orders and specific journals',
    'description': """
โมดูลล็อกภาษีสำหรับการขายและเช่า

ฟีเจอร์:
- ล็อกภาษีใน sale.order.line ประเภทขาย เป็น ภาษีขายไม่รวม Vat 7%
- ล็อกภาษีใน sale.order.line ประเภทเช่า เป็น ภาษีขายยังไม่ถึงกำหนด Vat 7%
- ล็อกภาษีใน account.move.line สำหรับสมุดรายวันเช่า, ค่าปรับหาย, ค่าปรับชำรุด
- ล็อกภาษีใน account.move.line สำหรับสมุดรายวันลดหนี้ขาย เป็น ภาษีขายรวม VAT 7%
- เพิ่มสิทธิ์ bypass สำหรับผู้ใช้งาน
    """,
    'author': 'NPD Development',
    'depends': ['sale', 'account', 'base', 'pfb_npd_add_date_quatation_order'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
