{
    'name': 'เพิ่มแท็บการตลาดในใบเสนอขาย',
    'version': '14.0.1.0.0',
    'summary': 'เพิ่มแท็บ Marketing ในแบบฟอร์มใบเสนอขาย (Sale Order)',
    'description': '''
        โมดูลนี้จะเพิ่มแท็บ "การตลาด" (Marketing) ในแบบฟอร์มของใบเสนอขาย 
        ซึ่งประกอบด้วยฟิลด์แคมเปญ สื่อ และแหล่งที่มา สำหรับใช้วิเคราะห์ทางการตลาด
    ''',
    'category': 'การขาย',
    'author': 'NPD',
    'website': 'https://www.npd9.com',
    'depends': ['sale', 'utm'],  # ต้องพึ่งพาโมดูล sale และ utm
    'data': [
        'security/ir.model.access.csv',
        'data/customer_channel_data.xml',
        'data/freelance_salesperson_data.xml',
        'views/customer_channel.xml',
        'views/freelance_salesperson.xml',
        'views/sale_order.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
