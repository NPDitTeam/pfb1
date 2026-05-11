# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'NPD Odoo 14 Budget',
    'version': '14.0.1.0',
    'category': 'Accounting',
    'summary': 'Accounting Budgeting',
    'live_test_url': '',
    'sequence': '8',
    'website': 'https://npd9.com/',
    'author': 'wattanadev',
    'maintainer': 'thaiodoo',
    'license': 'LGPL-3',
    'support': 'info@thaiodoo.com',
    'website': '',
    'depends': [
                'budget_control',
                'budget_activity',
                'budget_activity_expense',
                'budget_activity_contract',
                'budget_activity_purchase',
                'budget_activity_advance_clearing',
                'budget_activity_purchase_request',
                'budget_allocation',
                'budget_allocation_dimension',
                'budget_allocation_dimension_fund',
                'budget_allocation_plan_revision',
                'budget_allocation_transfer',
                'budget_control_consumed_plan',
                'budget_control_department',
                'budget_control_exception',
                'budget_control_operating_unit',
                'budget_control_operating_unit_access_all',
                'budget_control_revision_operating_unit',

                'budget_control_rolling',
                'budget_control_rolling_revision',
                'budget_control_sequence',
                'budget_control_transfer_dimension',
                'budget_control_transfer_dimension_constraint',
                'budget_control_transfer_fund',
                'budget_control_transfer_operating_unit',

                'budget_dimension',
                'budget_generate_analytic',
                'budget_job_order',
                'budget_plan_excel',
                'res_program',
                'res_project',
                'res_project_monitoring',
                'res_project_sequence',










                ],

    'demo': [],
    'data': [
        # 'views/account.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
    'qweb': [],
}
