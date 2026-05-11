{
    'name': 'Account Branch Extension',
    'version': '14.0.1.0.0',
    'summary': 'Add branch_id to advance models',
    'category': 'Accounting',
    'author': 'Your Company',
    'depends': ['base', 'account_advance'],  # ปรับชื่อโมดูลตามจริง
    'data': [
        'views/account_branch_views.xml',
    ],
    'installable': True,
    'application': False,
}
