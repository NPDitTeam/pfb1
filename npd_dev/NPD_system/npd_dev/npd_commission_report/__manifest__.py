# -*- coding: utf-8 -*-
{
    'name': 'รายงานค่าคอมมิชชั่น',
    'version': '14.0.1.0.1',
    'category': 'Accounting',
    'summary': 'รายงานค่าคอมมิชชั่นจากข้อมูล Payment และ Invoice',
    'description': 'โมดูลรายงานค่าคอมมิชชั่น (สาขา และ Sales)',
    'author': 'NPD',
    'depends': ['base', 'account', 'branch'],
    'data': [
        'security/ir.model.access.csv',
        'views/commission_report_views.xml',
        'views/commission_report_sales_views.xml',
        'views/salary_branch_report_views.xml',
        'data/salary_branch_report_cron.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
