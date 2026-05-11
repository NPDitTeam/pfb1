# -*- coding: utf-8 -*-
{
    'name': 'NPD CRM Call Button',
    'version': '14.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'เพิ่มปุ่มโทรหาลูกค้าและส่งเมลในหน้า CRM Lead',
    'description': '''
        เพิ่มปุ่มโทรหาลูกค้าและส่งเมลในหน้า CRM Lead Form
        โดยอ้างอิงฟังก์ชันจากโมดูล npd_call_lead
    ''',
    'author': 'NPD',
    'depends': ['crm', 'mail', 'npd_call_lead'],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
