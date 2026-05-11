# -*- coding: utf-8 -*-

{
    'name': 'Transport Management System',
    'category': 'Industries',
    'summary': """Manage Freight Transportation Management and Logistics System which has key features which include transporter details.
                Vehicle,route LR number of parcelinformation for  all delivery order details. 
                Create auto entry transport entry with reporting those entries make it more easy to operate Transport details in Odoo. 
                Manage Trans-shipment and vehicle by transporter and Transport Delivery Charge.
                Freight Transport Management and Delivery Routes
                Delivery Transport Mangement with Freight
                Transport for Delivery and Picking Order
    """,
    'version': '15.0',
    'description':"""This application allows you to manage Truckload Freights and Less-than-truckload freight by owner-operators, 
                    carriers, brokers and shippers.""",
    'depends': ['sale_management','stock','sale_stock','fleet','delivery',],
    'data': [
        'security/ir.model.access.csv',
        'views/transport_view.xml',
        # 'views/dashboard_view.xml',
        'views/sale_view.xml',
        'views/stock_picking_view.xml',
        'views/sale_report.xml',
        'views/delivery_report.xml',
        'views/account_invoice_view.xml',
        'views/partner_view.xml',
        'views/fleet_vehicle_view.xml',
        'views/picking_transport_info_view.xml',
        'views/transporter_route_view.xml',
        'views/transport_driver_view.xml',
        'views/shipment_view.xml',
        'views/transport_location_view.xml',
        'views/route_location_view.xml',
        'views/picking_route_view.xml',
        'wizard/sale_wizard_view.xml',
        'report/picking_transport_report.xml',
        'data/transport_sequence.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'pways_transportor_management/static/src/css/dashboard.css',
            'pways_transportor_management/static/src/js/dashboard_view.js',
        ],
        'web.assets_qweb': [
            'pways_transportor_management/static/src/xml/dashboard_view.xml',
        ],
    },
    'author': 'Preciseways',
    'website': "http://www.preciseways.com",
    'application': True,
    'installable': True,
    'price': 31,
    'currency': 'EUR',
    "images":['static/description/banner.png'],
    'license': 'OPL-1',
}