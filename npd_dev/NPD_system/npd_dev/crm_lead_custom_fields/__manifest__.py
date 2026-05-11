{
    'name': 'CRM Lead Custom Fields',
    'version': '14.0.1.0.0',
    'summary': 'เพิ่มฟิลด์หน้างานและสินค้าที่สนใจใน CRM Lead',
    'description': """
        โมดูลนี้เพิ่มฟิลด์เพิ่มเติมใน CRM Lead:
        - หน้างาน (Job Position)
        - สินค้าที่สนใจ (Products of Interest)
    """,
    'author': 'Your Company',
    'category': 'Sales/CRM',
    'depends': ['crm'],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}