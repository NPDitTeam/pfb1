# -*- coding: utf-8 -*-
{
    'name': 'NPD Quotation Total Lock',
    'version': '14.0.1.0.0',
    'category': 'Sales',
    'summary': 'ยึดยอดใบสั่งขายให้ตรงใบเสนอราคาตอน Convert to Order (กัน drift ปัดเศษ)',
    'description': """
NPD Quotation Total Lock
========================
พนักงานเปิดใบเสนอราคาให้ลูกค้าก่อน ลูกค้าได้ยอดนั้นไปแล้ว จากนั้นกด
"Convert to Order" (sale_isolated_quotation) ซึ่งใช้ self.copy() สร้างใบ
สั่งขายใหม่ → npd_rent_price_round.copy() คำนวณ VAT ใหม่ → ยอดอาจ drift
จากใบเสนอราคาเดิม (เช่น 0.10 บาท)

โมดูลนี้ override action_convert_to_order: หลัง copy เสร็จ จะ freeze ยอดใบ
สั่งขาย (บรรทัด + หัวเอกสาร) ให้ตรงกับใบเสนอราคา — เฉพาะเมื่อส่วนต่าง
≤ 1.00 บาท (drift ปัดเศษ) ถ้าต่างเกินนั้น (น่าจะแก้รายการจริง) จะไม่กลบยอด
แต่ log + แจ้งใน chatter ให้ตรวจสอบ
    """,
    'author': 'NPD Dev',
    'depends': [
        'sale',
        'sale_isolated_quotation',
        'npd_rent_price_round',
    ],
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
