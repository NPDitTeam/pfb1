# -*- coding: utf-8 -*-
# ทำต่อจาก l10n_th_tax_report (Ecosoft / OCA) โดยเปลี่ยนแหล่งข้อมูล
# จาก "ใบแจ้งหนี้" (account.move.tax.invoice) มาเป็น "การชำระ" (account.payment)

{
    "name": "Thai Tax Reports Payment",
    "version": "14.0.1.0.0",
    "author": "NPD IT Team",
    "license": "AGPL-3",
    "category": "Accounting",
    "summary": "รายงานภาษีขายที่ดึงยอดจากใบรับชำระ (account.payment) แทนใบแจ้งหนี้",
    "description": """
Thai Tax Reports Payment
========================
ก๊อปจากโมดูล Thai Tax Reports (l10n_th_tax_report) แล้วเปลี่ยนที่มาของข้อมูล

  เดิม  : ดึงจากใบแจ้งหนี้ (account_move_tax_invoice + account_move_line)
  ใหม่  : ดึงจากการชำระ (account.payment) สถานะ posted ตามช่วงวันที่ที่เลือก

  ยอดเงินใช้ฟิลด์ Payment Amount (account.payment.payment_amount)
    Base Amount = Payment Amount ถอด VAT  = payment_amount / 1.07
    Tax Amount  = Base Amount x 7%

  ตอนเปิดหน้าจอ ระบบเลือก Tax Group = VAT 7% และ Tax = ภาษีขาย Vat 7% ให้เลย
""",
    "depends": [
        "date_range",
        "report_xlsx_helper",
        "l10n_th_partner",
        "branch",
        "account_payment_invoice",
    ],
    "data": [
        "security/branch_model_access.xml",
        "security/ir.model.access.csv",
        "data/paper_format.xml",
        "data/report_data.xml",
        "reports/tax_payment_report.xml",
        "wizard/tax_payment_report_wizard_view.xml",
    ],
    "installable": True,
}
