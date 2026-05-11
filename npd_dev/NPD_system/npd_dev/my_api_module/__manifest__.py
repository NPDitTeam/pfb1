{
    'name': 'My API Module',
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'views/users_view.xml',
    ],
    'external_dependencies': {'python': ['requests']},  # ถ้าใช้ requests
    'installable': True,
    'auto_install': False,
    'application': False,
}
