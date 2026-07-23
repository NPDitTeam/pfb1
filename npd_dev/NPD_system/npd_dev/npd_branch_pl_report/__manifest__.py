# -*- coding: utf-8 -*-
{
    'name': 'งบรายรับ-รายจ่ายรายสาขา',
    'version': '14.0.1.0.0',
    'category': 'Accounting',
    'summary': 'งบรายรับ-รายจ่ายรายสาขา แยกตามรหัสบัญชี x รายเดือน (ดึงจาก GL)',
    'description': """
งบรายรับ-รายจ่ายรายสาขา (Branch P&L by month)
=============================================
- เลือก ปี + สาขา แล้วออกรายงานแยกตามรหัสบัญชี x 12 เดือน + รวม
- ดึงจากบัญชีแยกประเภท (account.move.line) ที่ posted ของสาขานั้น
- แถวรายได้ (บัญชีกลุ่มรายได้) / แถวรายจ่าย (บัญชีกลุ่มค่าใช้จ่าย + บัญชีภาษีซื้อ)
- รวมรายจ่าย และ คงเหลือ (= รายได้ - รายจ่าย)
- เงื่อนไขการกรอง (สาขา/งวด/posted) แนวเดียวกับคอลัมน์ 'รายจ่ายรวม' ในโมดูล commission
  เพื่อให้ยอดรวมรายเดือน reconcile กัน
""",
    'author': 'NPD',
    'depends': ['base', 'account', 'branch'],
    'data': [
        'security/ir.model.access.csv',
        'views/branch_pl_report_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
