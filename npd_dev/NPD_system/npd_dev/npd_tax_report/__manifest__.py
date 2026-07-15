# -*- coding: utf-8 -*-
{
    "name": "NPD - TAX Report (Custom)",
    "summary": "รายงานภาษี (VAT/TAX Report) ดูและกรองผ่านระบบ Odoo ได้โดยตรง",
    "version": "14.0.2.3.0",
    "author": "NPD",
    "license": "AGPL-3",
    "category": "Accounting",
    "depends": [
        "account",
        "l10n_th_partner",
        "l10n_th_tax_invoice",
        "branch",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/tax_report_views.xml",
    ],
    "installable": True,
    "application": False,
}
