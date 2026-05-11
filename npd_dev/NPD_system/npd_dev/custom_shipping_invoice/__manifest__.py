{
    'name': 'Custom Shipping Invoice',
    'version': '1.0',
    'summary': 'Add shipping cost button and invoice integration',
    'author': 'Your Name',
    'category': 'Sales',
    'depends': ['sale', 'account', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'security/popup_shipping_invoice_rules.xml',
        'views/sale_order_view.xml',
        'views/popup_shipping_invoice.xml',
    ],
    'installable': True,
    'application': False,
}
