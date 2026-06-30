# -*- coding: utf-8 -*-
{
    "name": "รายงานสัญญาเช่าอุปกรณ์ก่อสร้าง (QWeb)",
    "summary": "พิมพ์สัญญาเช่าอุปกรณ์ก่อสร้างจากใบขาย เลขที่สัญญา prefix ตาม DB + ir.sequence",
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "author": "NPD Custom",
    "category": "Sales",
    "depends": ["sale"],
    "data": [
        "security/ir.model.access.csv",
        "data/paper_format.xml",
        "data/ir_sequence.xml",
        "views/contract_prefix_wizard_view.xml",
        "views/sale_order_view.xml",
        "reports/rental_contract_report.xml",
    ],
    "installable": True,
    "application": False,
}
