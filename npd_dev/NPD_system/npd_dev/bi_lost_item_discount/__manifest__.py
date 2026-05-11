# -*- coding: utf-8 -*-
{
    'name': 'Lost Item Discount Calculation',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Special discount calculation for lost items (สินค้าหาย)',
    'description': """
        Adds special field for lost item discount calculation
        - Calculates: quantity * price_unit - discount_amount
        - Only applies when reason code is 'สินค้าหาย' with fixed discount
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'account',
        'bi_sale_purchase_discount_with_tax','scrap_reason_code'  # หรือโมดูลที่มี wt_tax_id
    ],
    'data': [
        'views/account_move_line_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}