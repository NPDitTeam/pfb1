# -*- coding: utf-8 -*-
{
    'name': 'NPD Product Withholding Tax',
    'version': '14.0.1.1.0',
    'summary': 'Auto-create WHT accounts and link products to withholding tax configuration',
    'description': """
        - เพิ่มฟิลด์ Withholding Tax บน Product Template
        - สร้าง Withholding Tax Account อัตโนมัติตามประเภทค่าใช้จ่าย
        - Auto-fill WHT เมื่อเลือกสินค้าใน Advance Clear
        - รองรับอัตรา WHT: 1%, 2%, 3%, 5%
    """,
    'category': 'Accounting',
    'author': 'NPD Dev',
    'depends': [
        'base',
        'account',
        'product',
        'account_advance',
        'l10n_th_withholding_tax_cert',
        'withholding_tax_cert_amount',
        'withholding_tax_branch',
        'account_voucher',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/wht_account_data.xml',
        'views/product_template_views.xml',
        'views/wht_category_views.xml',
        'views/account_voucher_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
