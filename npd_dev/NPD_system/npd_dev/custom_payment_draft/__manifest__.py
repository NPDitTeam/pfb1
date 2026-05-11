{
    'name': 'Custom Payment Draft Reset',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'summary': 'ยกเลิกการรับชำระเงินเมื่อรีเซ็ตเป็นแบบร่าง',
    'description': """
        เมื่อกดปุ่มรีเซ็ตเป็นแบบร่างใน Invoice/Bill
        จะยกเลิกการรับชำระเงินที่เกี่ยวข้องทั้งหมด
    """,
    'depends': ['account','account_payment_invoice'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}