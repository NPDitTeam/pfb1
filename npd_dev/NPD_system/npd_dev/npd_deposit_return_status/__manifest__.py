# -*- coding: utf-8 -*-
{
    'name': 'NPD Deposit Return Status',
    'version': '14.0.1.0.0',
    'summary': 'ติดตามสถานะการคืนเงินประกันในใบสั่งขาย',
    'description': """
        เพิ่มฟิลด์สถานะการคืนเงินประกันในตาราง sale.order
        - ลูกค้ายังไม่คืนสินค้า
        - สาขายังไม่สร้างการคืนเงินประกัน
        - รอคืนเงินประกันจากการเงิน
        โดยคำนวณจาก rental_status, stock.picking, account.voucher
    """,
    'author': 'NPD Dev',
    'category': 'Sales',
    'depends': ['sale', 'stock', 'account_voucher_npd', 'pfb_npd_add_date_quatation_order'],
    'data': [
        'views/sale_order_views.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
