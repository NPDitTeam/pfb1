{
    'name': 'NPD Remote Scrap API',
    'version': '1.0',
    'summary': 'ดึงข้อมูลสินค้าชำรุดจาก Odoo database อื่น ๆ ผ่าน JSON-RPC',
    'description': 'Service module สำหรับเรียก stock.scrap จาก Odoo server ภายนอก (เช่น NPD_Intertrading_New, NPD_Bangkok_New) ผ่าน /web/session/authenticate + /web/dataset/call_kw',
    'author': 'NPD',
    'category': 'Tools',
    'depends': ['base'],
    'data': [],
    'installable': True,
    'application': False,
    'external_dependencies': {
        'python': ['requests'],
    },
}
