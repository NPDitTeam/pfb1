# -*- coding: utf-8 -*-
{
    'name': 'NPD Analytic Branch Required',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'summary': 'บังคับเลือกสาขา (Branch) ทุกครั้งที่สร้าง Analytic Account',
    'description': '''
        โมดูลนี้บังคับให้ต้องเลือก field "สาขา" (branch_id)
        ทุกครั้งที่สร้าง/บันทึก account.analytic.account ใหม่
        เพื่อป้องกันข้อมูลตกหล่นในรายงานที่ดึงค่าใช้จ่าย/ค่าคอมตามสาขา
        (เช่น รายงานค่าคอมมิชชั่น และหน้าทำเงินเดือน)
    ''',
    'author': 'NPD',
    'depends': [
        'npd_analytic_branch',
    ],
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
