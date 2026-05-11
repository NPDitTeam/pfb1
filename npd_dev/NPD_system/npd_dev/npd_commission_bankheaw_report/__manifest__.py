# -*- coding: utf-8 -*-
{
    'name': 'รายงานค่าคอมบ้านเขียว',
    'version': '14.0.1.0.0',
    'summary': 'รายงานค่าคอมมิชชั่นบ้านเขียว',
    'description': """
        รายงานค่าคอมมิชชั่นบ้านเขียว
        - ดึงข้อมูลจากฐานข้อมูล npd_db
        - แสดงยอดรายได้รวม, ค้างชำระ, รับชำระหนี้เก่า
        - รายงานตามเซลล์
    """,
    'author': 'NPD',
    'category': 'Accounting/Reporting',
    'depends': ['base', 'account', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/sales_commission_report_views.xml',
        'data/ir_cron_data.xml',
    ],
    'external_dependencies': {
        'python': ['pymysql'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
