{
    'name': 'ตรวจสอบสต็อกสินค้าด้วยบาร์โค้ด',
    'version': '1.0',
    'summary': 'ตรวจสอบสต็อกสินค้าโดยการสแกนบาร์โค้ดหรือเลือกสินค้าเอง',
    'depends': ['base', 'sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_stock_check_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo14_barcode_stock/static/src/js/barcode_auto_enter.js',
        ],
    },
    'installable': True,
    'application': False,
}
