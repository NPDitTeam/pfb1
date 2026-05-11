{
    'name': 'PFB NPD : all Customs',
    'version': '14.0.1.0.0',
    'author': 'PP',
    'license': 'AGPL-3',
    'website': '',
    'category': 'Fields',
    'depends': ['sale', 'sale_invoice_plan', 'sale_order_line_menu'],

    'data': [
        'security/ir.model.access.csv',
        'wizard/sale_make_invoice_rent_views.xml',
        'views/product_template.xml',
        'views/product_pricelist.xml',
        'views/sale_order.xml',
        'views/sale_objective.xml',
        'views/account_move.xml',
        'views/res_config_settings.xml',

    ],
    'installable': True,
}
