{
    'name': 'Adjust Decimal',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'summary': 'ปรับแก้ทศนิยมยอดรวมในใบแจ้งหนี้',
    'description': """
        โมดูลสำหรับปรับแก้ทศนิยมของยอดรวมในรายการใบแจ้งหนี้
        - แสดงปุ่ม "แก้ไขทศนิยม" เฉพาะสถานะฉบับร่าง
        - เปิด popup สำหรับแก้ไขทศนิยมของยอดรวมแต่ละรายการ
        - คำนวณราคาใหม่อัตโนมัติ
    """,
    'author': 'NPD',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/decimal_adjustment_wizard_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
