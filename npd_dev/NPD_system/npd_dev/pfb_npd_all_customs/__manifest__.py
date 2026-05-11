{
    'name': 'PFB NPD : all Customs',
    'version': '14.0.1.0.0',
    'author': 'PP',
    'license': 'AGPL-3',
    'website': '',
    'category': 'Fields',
    'depends': ['sale','sale_invoice_plan','sale_order_line_menu'],

    'data': [
        'views/product_template.xml',
        'views/product_pricelist.xml',
        'views/sale_order.xml',
    ],
    'installable': True,
}
