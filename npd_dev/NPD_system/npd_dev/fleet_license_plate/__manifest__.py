{
    'name': 'ทะเบียนรถใน Sale',
    'version': '14.0.1.0.0',
    'summary': 'ระบบเก็บข้อมูลทะเบียนรถ พร้อมผูกพนักงานขับรถ',
    'category': 'Sales',
    'author': 'Your Name',
    'depends': ['sale', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/fleet_license_plate_views.xml',
        'views/fleet_license_plate_menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
