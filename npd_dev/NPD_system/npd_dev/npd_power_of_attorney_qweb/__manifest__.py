# -*- coding: utf-8 -*-
{
    "name": "รายงานหนังสือมอบอำนาจ (QWeb)",
    "summary": "พิมพ์หนังสือมอบอำนาจจากใบขาย ฟอนต์/ขนาดเดียวกับสัญญาเช่าอุปกรณ์ก่อสร้าง",
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "author": "NPD Custom",
    "category": "Sales",
    # depend โมดูลสัญญาเช่า เพื่อใช้ฟอนต์ + helper (ชื่อบริษัท/ลูกค้า/เลขสัญญา/วันที่ไทย) ซ้ำ
    "depends": ["sale", "npd_rental_equipment_contract_qweb"],
    "data": [
        "reports/power_of_attorney_report.xml",
    ],
    "installable": True,
    "application": False,
}
