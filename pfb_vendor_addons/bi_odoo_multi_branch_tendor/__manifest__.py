# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Multiple Branch Unit Operations for Purchase Requisition and Tendor Odoo',
    'version': '14.0.0.0',
    'category': 'Purchase',
    'summary': 'Multiple Branch Management Tender Multi Branch Purchase Requisition app Multiple Unit Operating unit tender multi branch tender multi branch Purchase Requisition branch tender Purchase unit for single company with Multi Branches multi company',
    "description": """
        Multiple Unit operation management for single company, Mutiple Branch management for single company, multiple operation for single company.
        Branch for POS, Branch for Sales, Branch for Purchase, Branch for all, Branch for Accounting, Branch for invoicing, Branch for Payment order, Branch for point of sales, Branch for voucher, Branch for All Accounting reports, Branch Accounting filter.Branch for warehouse, branch for sale stock, branch for location
        Unit for POS, Unit for Sales, Unit for Purchase, Unit for all, Unit for Accounting, Unit for invoicing, Unit for Payment order, Unit for point of sales, Unit for voucher, Unit for All Accounting reports, Unit Accounting filter.branch unit for warehouse, branch unit for sale stock, branch unit for location
        Unit Operation for POS, Unit Operation for Sales, Unit operation for Purchase, Unit operation for all, Unit operation for Accounting, Unit Operation for invoicing, Unit operation for Payment order, Unit operation for point of sales, Unit operation for voucher, Unit operation for All Accounting reports, Unit operation Accounting filter.
        Branch Operation for POS, Branch Operation for Sales, Branch operation for Purchase, Branch operation for all, Branch operation for Accounting, Branch Operation for invoicing, Branch operation for Payment order, Branch operation for point of sales, Branch operation for voucher, Branch operation for All Accounting reports, Branch operation Accounting filter.


        operating unit for company.
        Multiple Branch Operation Setup for Human Resource
        Unit Operation Setup for Human Resource

        Multiple Branch Operation Setup for Tendor
        multiple Unit Operation Setup for Tendor
        multiple branch for purchase tendor
        multiple branch for purchase Requisition
        multiple branch for purchases tendor
        multiple branch for purchases Requisition
        multiple branch for Requisition of purchase
        multiple branch for request for purchase
        multiple branch for purchase request

        multiple Unit Operation Setup for purchase tendor
        multiple Unit Operation Setup for purchase Requisition
        multiple Unit Operation Setup for purchases tendor
        multiple Unit Operation Setup for purchases Requisition
        multiple Unit Operation Setup for Requisition of purchase
        multiple Unit Operation Setup for request for purchase
        multiple Unit Operation Setup for purchase request

        multiple Unit Operation for purchase tendor
        multiple Unit Operation for purchase Requisition
        multiple Unit Operation for purchases tendor
        multiple Unit Operation for purchases Requisition
        multiple Unit Operation for Requisition of purchase
        multiple Unit Operation for request for purchase
        multiple Unit Operation for purchase request
        multi branch purchase tendor
        purchase tendor branch
        purchase tendor operating unit
        purchase tendor unit operation management
        purchase tendor multiple unit
        operating unit purchase tendor
        operating unit tendor
        tendor operating unit
        multi branch tendor
        multi branch management
        multi branch application
        multi operation unit application multi branch odoo multi branch
        all in one multi branch application multi branch unit operation multi unit operation branch management
        odoo multi branches management application multi operation mangement
        purchase tendor multi branch
        purchase tendor multiple operating unit
        purchase tendor multi unit operation management
        multi branch purchase tendor multiple unit
        multi operating unit purchase tendor
        operating unit tendor for multi branch
        tendor operating unit


        operating Unit for POS,operating Unit for Sales,operating Unit for Purchase,operating Unit for all,operating Unit for Accounting,operating Unit for invoicing,operating Unit for Payment order,operating Unit for point of sales,operating Unit for voucher,operating Unit for All Accounting reports,operating Unit Accounting filter. Operating unit for picking, operating unit for warehouse, operaing unit for sale stock, operating unit for location
        operating-Unit Operation for POS,operating-Unit Operation for Sales,operating-Unit operation for Purchase,operating-Unit operation for all, operating-Unit operation for Accounting,operating-Unit Operation for invoicing,operating-Unit operation for Payment order,operating-Unit operation for point of sales,operating-Unit operation for voucher,operating-Unit operation for All Accounting reports,operating-Unit operation Accounting filter.
    """,
    'author': 'BrowseInfo',
    'website': 'https://www.browseinfo.in',
    "price": 20.00,
    "currency": 'EUR',
    'depends': ['base','branch','purchase','purchase_requisition'],
    'data': [
                'security/purchase_requisition_branch_security.xml',
                'views/purchase_branch_view.xml',
             ],
    'qweb': [],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'live_test_url':'https://youtu.be/t1j6-QcquJA',
    "images":['static/description/Banner.png'],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
