# Copyright 2019 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

{
    "name": "Purchase Invoice Plan Inherit",
    "summary": "Purchase Invoice Plan Inherit",
    "version": "14.0.1.3.1",
    "author": "PFB",
    "license": "AGPL-3",
    "website": "",
    "category": "Purchase",
    "depends": ["purchase", "purchase_invoice_plan", "purchase_open_qty"],
    "data": [
        'security/security.xml',
        "wizard/view_purchase_create_invoice_plan.xml",
        "views/purchase_view.xml",
        "views/purchase_invoice_planview.xml",
    ],
    "installable": True,
    "development_status": "Alpha",
}
