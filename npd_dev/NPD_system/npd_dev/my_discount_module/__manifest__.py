# my_discount_module/__manifest__.py
{
    'name': 'Purchase Order Discount',
    'version': '14.0.1.0.0',
    'summary': 'Add discount field to purchase order lines.',
    'description': """
        This module adds a discount field to the purchase order lines, allowing users
        to apply a percentage discount to each product.
    """,
    'author': 'Your Name',
    'website': 'http://www.yourwebsite.com',
    'category': 'Purchases',
    'depends': ['purchase'],
    'data': [
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}