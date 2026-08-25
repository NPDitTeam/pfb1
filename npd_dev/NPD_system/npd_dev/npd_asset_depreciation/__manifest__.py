# -*- coding: utf-8 -*-
{
    'name': 'NPD Asset Depreciation',
    'version': '14.0.8.1.0',
    'summary': 'ค่าเสื่อมราคาสินทรัพย์รายเดือน 12 เดือน แบบตัดตามวันจริง (ตามไฟล์ Excel ค่าเสื่อม 5 บริษัท)',
    'description': """
ค่าเสื่อมราคาสินทรัพย์แบบ NPD
=============================
คำนวณค่าเสื่อมราคาแบบเดียวกับไฟล์ Excel "ค่าเสื่อม นภดล 5 บริษัท"

    จำนวนวัน   = เดือนที่ซื้อ    -> สิ้นเดือน - วันที่ซื้อ + 1
                 เดือนถัดไป     -> จำนวนวันเต็มเดือน
    ค่าเสื่อม   = ราคาทรัพย์สิน x ร้อยละต่อปี x จำนวนวัน / 365
    เพดาน      = ยอดยกมา - มูลค่าซาก (ปกติ 1 บาท) ค่าเสื่อมเกินเพดานให้ตัดแค่เพดาน
    ยอดยกมา <= มูลค่าซาก -> ค่าเสื่อม 0
    ซื้อหลังสิ้นเดือน       -> ยังไม่เริ่มคิด

รองรับการนำเข้ายอดยกมาปัจจุบัน (ยกยอดจากระบบเดิม/ไฟล์ Excel) แล้วให้ระบบ
คำนวณต่อไปข้างหน้าเอง โดยไม่ต้องไล่คำนวณย้อนหลังตั้งแต่วันที่ซื้อ
    """,
    'category': 'Accounting',
    'author': 'NPD Dev',
    'depends': [
        'base',
        'account',
        'account_asset_management',
        # ให้ชื่อฟิลด์ทะเบียนทรัพย์สินเป็นไทยได้ และมั่นใจว่าโหลดหลังโมดูลนั้น
        'pfb_std_asset_free_field',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'views/account_asset_labels.xml',
        'views/account_asset_views.xml',
        'views/depreciation_line_views.xml',
        'views/depreciation_year_views.xml',
        'views/depreciation_summary_views.xml',
        'report/tax_depreciation_report.xml',
        'wizard/depreciation_compute_views.xml',
        'views/menu.xml',
        'views/hide_legacy_menu.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
