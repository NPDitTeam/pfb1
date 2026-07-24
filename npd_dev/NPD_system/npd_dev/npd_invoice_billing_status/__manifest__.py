{
    'name': 'NPD Invoice Billing Status',
    'summary': 'เพิ่มสถานะวางบิล ช่องทางวางบิล และแนบหลักฐานการวางบิล บนใบแจ้งหนี้',
    'version': '1.0',
    'depends': ['npd_print_select_account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
