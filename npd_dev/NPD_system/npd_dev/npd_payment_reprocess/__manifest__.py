{
    'name': 'NPD Payment Reprocess',
    'version': '14.0.1.1.0',
    'summary': 'ดำเนินการรับชำระใหม่อัตโนมัติ (Reset → Refresh Invoice → Post)',
    'description': """
        โมดูลสำหรับดำเนินการรับชำระใหม่:
        - เพิ่มปุ่ม "ดำเนินการรับชำระใหม่" บนหน้า Payment
        - แสดง Popup ค้นหาด้วยช่วงวันที่/เวลา
        - อัตโนมัติ: Reset to Draft → Refresh Invoice IDs → Post ใหม่
        - ควบคุมสิทธิ์ผ่าน checkbox ในหน้าผู้ใช้
    """,
    'category': 'Accounting',
    'author': 'NPD Dev',
    'website': '',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'account',
        'account_payment_invoice',
    ],
    'data': [
        'security/reprocess_security.xml',
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/payment_reprocess_wizard_view.xml',
        'views/account_payment_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
