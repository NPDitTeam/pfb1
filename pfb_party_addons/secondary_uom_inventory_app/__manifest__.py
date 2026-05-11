# -*- coding: utf-8 -*-

{
    'name' : "Inventory Secondary Unit of Measure-UOM",
    "author": "Edge Technologies",
    'version': '14.0.1.0',
    'live_test_url': "https://youtu.be/hmzRJ-4WE0k",
    "images":['static/description/main_screenshot.png'],
    'summary': 'Inventory Secondary Unit of Measure for Inventory Secondary Unit of Measure for Warehouse Secondary Unit of Measure Product Secondary UOM Inventory Secondary UOM for Warehouse Secondary UOM Product Secondary Unit of Measure for Picking Secondary UOM',
    'description' : '''
           Inventory Secondary Unit of Measure.
    
Secondary UOM
Stock in Different UOMs
UOM
Unit of Measure

    ''',
    "license" : "OPL-1",
    'depends' : ['stock','stock_picking_cancel_extended'],
    'data': [
            'security/ir.model.access.csv',
            'security/secondary_uom_group.xml',
            'views/product_view.xml',
            'views/stock_move_view.xml',
            'views/stock_inventory_view.xml',
            'views/stock_quant_view.xml',
            'views/stock_scrap_view.xml',
            'views/inventory_report_template.xml',

             ],
    'installable': True,
    'auto_install': False,
    'price': 15,
    'currency': "EUR",
    'category': 'Warehouse',
}



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
