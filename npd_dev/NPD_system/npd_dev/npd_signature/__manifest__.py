# -*- coding: utf-8 -*-
{
    'name': 'ลายเซ็น (Signature)',
    'version': '14.0.1.0.0',
    'category': 'Tools',
    'summary': 'ระบบจัดการลายเซ็น - เซ็นผ่านระบบ และแปลงข้อความเป็นลายเซ็น',
    'description': """
        ระบบจัดการลายเซ็น NPD
        =====================
        - เซ็นลายเซ็นผ่านระบบ (Signature Pad)
        - แปลงข้อความเป็นลายเซ็น (Text to Signature)
        - จัดเก็บลายเซ็นของพนักงาน
    """,
    'author': 'NPD Development',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base', 'hr', 'web', 'mail'],
    'data': [
        'security/signature_security.xml',
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/signature_views.xml',
        'views/menu.xml',
    ],
    'qweb': [
        'static/src/xml/signature_widget.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
}
