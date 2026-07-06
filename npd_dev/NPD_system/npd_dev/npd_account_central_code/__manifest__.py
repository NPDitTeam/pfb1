{
    'name': 'NPD Account Central Code',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'เพิ่มฟิลด์รหัสบัญชีกลาง (กรอกเฉพาะตัวเลข) ในผังบัญชี',
    'description': """
        เพิ่มฟิลด์ "รหัสบัญชีกลาง" (central_account_code) ในผังบัญชี account.account
        โดยสามารถกรอกได้เฉพาะตัวเลขเท่านั้น
    """,
    'author': 'NPD IT',
    'depends': ['account'],
    'data': [
        'views/account_account_view.xml',
    ],
    'installable': True,
    'application': False,
}
