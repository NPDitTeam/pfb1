{
    'name': 'Stock Picking Rent Discount & Approval',
    'version': '14.0.1.0.0',
    'summary': 'Add rental discount and approval process in Stock Picking',
    'category': 'Stock',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        # wizard views
        'views/rent_discount_wizard_view.xml',
        'views/approval_picking_wizard_view.xml',
        'views/request_picking_approval_wizard_view.xml',
        # main picking view
        'views/stock_picking_view.xml',
    ],
    'installable': True,
    'application': False,
}
