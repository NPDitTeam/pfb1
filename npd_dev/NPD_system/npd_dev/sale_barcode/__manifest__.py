{
    'name': 'Sale Barcode Scanner',
    'version': '1.0',
    'depends': ['sale'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sale_barcode/static/src/js/sale_barcode.js',  # ต้องระบุพาธนี้ให้ถูกต้อง
        ],
    },
    'installable': True,
    'auto_install': False,
}