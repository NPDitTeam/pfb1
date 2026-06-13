{
    'name': 'NPD ปัดเศษยอดรวม Sale Order',
    'version': '14.0.1.0.0',
    'category': 'Sales',
    'summary': 'ปุ่มปัดเศษทศนิยมยอดรวมในใบสั่งขาย เลือกขั้นการปัดและทิศทางได้',
    'description': """
ปัดเศษยอดรวม (amount_total) ของ Sale Order
=========================================
- เพิ่มปุ่ม "ปัดเศษยอดรวม" บนฟอร์มใบสั่งขาย
- เลือกขั้นการปัด (step) ได้ทั้งแบบ preset (0.05 / 0.10 / 0.25 / 0.50 / 1.00) และกรอกเอง
- เลือกทิศทางการปัดได้: ปัดเข้าใกล้สุด / ปัดขึ้น / ปัดลง
- ส่วนต่างจากการปัดถูกดูดเข้า amount_tax ทำให้ยอดรวมเปลี่ยนจริง และอยู่ถาวร (ไม่โดน recompute ทับ)
""",
    'author': 'NPD',
    'depends': ['sale'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/sale_order_rounding_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
