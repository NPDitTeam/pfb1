# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': "All in one Multiple Branch(Unit) Bundle Community Edition",
    'version': '14.0.0.1',
    'category': 'Sales',
    'summary': 'All Multiple Branch Multi Branch app Multiple Unit Operating unit sales branch Sales Purchase branch Invoicing branch billing Voucher branch warehouse branch Payment branch Accounting Reports All in one Multi Branch bundle All in one Multiple Branch bundle',
    'description': """

	""",
    'author': "BrowseInfo",
    'website': 'https://www.browseinfo.in',
    "price": 5.0,
    "currency": 'EUR',
    'depends': ['branch',
                # 'bi_branch_pos',
                'bi_branch_financial_report', 'bi_branch_partner_reports',
                'bi_branch_tax_accounting_reports', 'bi_odoo_crm_multi_branch',
                'bi_odoo_mrp_multi_branch', 'bi_odoo_multi_branch_tendor',
                'bi_odoo_multi_branch_project', 'bi_branch_assets_community',
                'bi_license_plate_hr_community', 'bi_branch_budget_community',
                'bi_branch_scrap_order', 'bi_multi_branch_pricelist'],
    'data': [],
    'qweb': [
    ],
    "auto_install": False,
    "installable": True,
    'live_test_url': 'https://youtu.be/ClI0_t0HVCY',
    "images": ["static/description/Banner.png"],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
