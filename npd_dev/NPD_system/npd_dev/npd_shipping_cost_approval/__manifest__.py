{
    'name': 'NPD : อนุมัติค่าขนส่งพิเศษ',
    'version': '14.0.1.2.0',
    'summary': 'ติ๊กค่าขนส่งพิเศษเป็น 0 หรือค่าขนส่งพิเศษต่ำกว่า 30% ของค่าขนส่งหลังปัดเศษ '
               'ต้องผ่านการอนุมัติก่อนยืนยันใบสั่งขาย (ใช้เฉพาะ NPD_Logistics_New)',
    'author': 'NPD Development',
    'license': 'AGPL-3',
    'category': 'Sales',
    'depends': ['sale', 'mail', 'pfb_npd_tap_shipment_information'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'wizard/shipping_cost_approval_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
