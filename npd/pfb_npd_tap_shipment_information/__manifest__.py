{
    'name': 'PFB NPD : Shipment Information',
    'version': '14.0.1.0.0',
    'author': 'PP',
    'license': 'AGPL-3',
    'category': 'Sale',
    'depends': ['sale', 'web' ,'shipping_cost', 'fleet_license_plate'],  # ✅ ต้องใช้ web เพื่อให้ JavaScript ทำงาน
    'data': [
        'views/assets.xml',  # ✅ โหลด JavaScript
        'views/sale_order.xml',  # ✅ โหลดหน้า Sales Order
    ],


    'installable': True,
}
