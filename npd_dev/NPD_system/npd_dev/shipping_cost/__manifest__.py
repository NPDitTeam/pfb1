{
    'name': 'Shipping cost ค่าขนส่ง',
    'version': '14.0.1.0.0',
    'summary': 'ระบบเก็บข้อมูลค่าขนส่ง ',
    'category': 'Sales',
    'author': 'Your Name',
    'depends': ['sale', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/shipping_cost_views.xml',
        'views/shipping_cost_menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
