# -*- coding: utf-8 -*-
# ต่อยอดจาก l10n_th_tax_report (Copyright 2019 Ecosoft Co., Ltd) License AGPL-3.0
"""รายงานภาษีที่ดึงข้อมูลจาก 'การชำระ' (account.payment) แทน 'ใบแจ้งหนี้'

ของเดิม (l10n_th_tax_report) ยิง SQL ที่ account_move_tax_invoice + account_move_line
ตัวนี้เปลี่ยนมาอ่าน account.payment ตรง ๆ เพราะ:

  - ยอดที่ต้องการคือฟิลด์ Payment Amount (account.payment.payment_amount)
    ซึ่งเป็น compute ที่ไม่ได้ store (payment_amount = amount - wht_amount)
    จึงยิง SQL ไม่ได้ ต้องอ่านผ่าน ORM
  - เงื่อนไข: state = 'posted' และวันที่ (account.payment.date ซึ่งมาจาก
    account.move ผ่าน _inherits) อยู่ในช่วง Period ที่เลือก

การคิดเงิน (ตามที่ผู้ใช้ระบุ 19 ส.ค. 2026):
    Base Amount = ถอด VAT ออกจาก Payment Amount = payment_amount / (1 + 7%)
    Tax Amount  = Base Amount x 7%
อัตราภาษีไม่ได้ fix 7% ในโค้ด แต่อ่านจาก account.tax.amount ของภาษีที่เลือก

ภาษีที่เลือกเป็นตัวกำหนดว่าจะเอาใบชำระฝั่งไหน
    ภาษีขาย (sale)     -> ใบรับชำระจากลูกค้า (payment_type = inbound)
    ภาษีซื้อ (purchase) -> ใบจ่ายชำระผู้ขาย   (payment_type = outbound)
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TaxPaymentReportView(models.TransientModel):
    _name = "tax.payment.report.view"
    _description = "Tax Payment Report View"
    _order = "id"

    name = fields.Char()                                   # Doc Ref.
    company_id = fields.Many2one("res.company")
    partner_id = fields.Many2one("res.partner")
    tax_id = fields.Many2one("account.tax")
    tax_base_amount = fields.Float()                       # ยอดถอด VAT แล้ว
    tax_amount = fields.Float()                            # VAT 7%
    payment_amount = fields.Float()                        # ยอดตามหน้าใบชำระ (รวม VAT)
    tax_date = fields.Char()                               # วันที่ของใบชำระ
    tax_invoice_number = fields.Char()                     # เลขรายการบันทึกบัญชี (RV-xxx)
    payment_id = fields.Many2one("account.payment", string="Payment")
    payment_name = fields.Char()                           # เลขใบชำระ (CUST.IN-xxx)
    invoice_name = fields.Char()                           # เลขใบแจ้งหนี้ที่ใบชำระอ้างถึง
    branch_id = fields.Many2one("res.branch")
    branch_name = fields.Char()


class TaxPaymentReport(models.TransientModel):
    _name = "report.tax.payment.report"
    _description = "Report Tax Payment Report"

    # Filters fields, used for data computation
    company_id = fields.Many2one(comodel_name="res.company")
    tax_id = fields.Many2many(comodel_name="account.tax")
    date_range_id = fields.Many2one(comodel_name="date.range")
    date_from = fields.Date()
    date_to = fields.Date()
    branch_id = fields.Many2one("res.branch", store=False)

    # บรรทัดของรายงาน
    #
    # โมดูลต้นทางประกาศฟิลด์นี้เป็น compute แต่ใน Odoo 14 เวอร์ชันนี้ compute
    # ไม่ถูกเรียกตอน template อ่าน o.results (ทดสอบกับ report.tax.report ของเดิม
    # ก็ได้ 0 บรรทัดเหมือนกัน) หน้า View/PDF จึงออกมาเป็นตารางเปล่า
    # ตัวนี้เลยเปลี่ยนเป็น Many2many ธรรมดา แล้วสร้างบรรทัดตอน create() แทน
    # ทุกทางที่เปิดรายงาน (View / PDF / Excel) จึงเห็นข้อมูลชุดเดียวกันแน่นอน
    results = fields.Many2many(
        comodel_name="tax.payment.report.view",
        string="Results",
    )

    @api.model_create_multi
    def create(self, vals_list):
        reports = super(TaxPaymentReport, self).create(vals_list)
        for report in reports:
            report._compute_results()
        return reports

    # ------------------------------------------------------------------
    # ดึงข้อมูล
    # ------------------------------------------------------------------
    def _payment_domain(self, tax):
        """domain หาใบชำระที่เข้าเงื่อนไขของภาษีตัวที่ส่งเข้ามา"""
        domain = [
            ("state", "=", "posted"),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
        ]
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        if self.branch_id:
            domain.append(("branch_id", "=", self.branch_id.id))
        # ภาษีขาย = เงินเข้า / ภาษีซื้อ = เงินออก (ภาษีที่ไม่ระบุด้าน เอาทั้งหมด)
        if tax.type_tax_use == "sale":
            domain.append(("payment_type", "=", "inbound"))
        elif tax.type_tax_use == "purchase":
            domain.append(("payment_type", "=", "outbound"))
        return domain

    def _payment_line_vals(self, payment, tax):
        """1 ใบชำระ -> 1 บรรทัดรายงาน (ถอด VAT ออกจาก Payment Amount)"""
        rate = (tax.amount or 0.0) / 100.0
        amount = payment.payment_amount or 0.0
        base = amount / (1.0 + rate) if rate else amount
        base = round(base, 2)
        return {
            "company_id": payment.company_id.id,
            "partner_id": payment.partner_id.id,
            "tax_id": tax.id,
            "payment_id": payment.id,
            "payment_amount": amount,
            "tax_base_amount": base,
            "tax_amount": round(base * rate, 2),
            "tax_date": payment.date and fields.Date.to_string(payment.date) or "",
            "tax_invoice_number": payment.move_id.name or "",
            "payment_name": payment.name or payment.move_id.name or "",
            "invoice_name": payment.search_invoice_name or "",
            "name": payment.ref or payment.payment_reference or "",
            "branch_id": payment.branch_id.id,
            "branch_name": payment.branch_id.name or "",
        }

    def _compute_results(self):
        """สร้างบรรทัดรายงานจากใบชำระ (เรียกให้เองตอน create)

        ชื่อเมธอดคงไว้ตามโมดูลต้นทาง เพราะ wizard ตอนทำไฟล์ Excel เรียกใช้ชื่อนี้
        """
        self.ensure_one()
        Payment = self.env["account.payment"]
        ReportLine = self.env["tax.payment.report.view"]

        vals_list = []
        if self.date_from and self.date_to:
            for tax in self.tax_id:
                payments = Payment.search(self._payment_domain(tax))
                # เรียงตามวันที่แล้วค่อยเลขที่ใบชำระ (ไม่ sort ใน search เพราะ
                # date เป็นฟิลด์ที่ยืมมาจาก account.move ผ่าน _inherits)
                payments = payments.sorted(
                    key=lambda p: (p.date or fields.Date.today(), p.name or ""))
                for payment in payments:
                    if not payment.payment_amount:
                        continue
                    vals_list.append(self._payment_line_vals(payment, tax))

        # ใช้ create() ไม่ใช่ new() เพราะบรรทัดต้องอยู่ยาวข้ามรีเควสต์ (ตอนกด
        # พิมพ์ PDF เบราว์เซอร์ยิงมาอีกรอบหนึ่ง) ตารางนี้เป็น TransientModel
        # Odoo เก็บกวาดให้เองอยู่แล้ว
        self.results = ReportLine.create(vals_list) if vals_list else False

    # ------------------------------------------------------------------
    # พิมพ์ / แสดงผล
    # ------------------------------------------------------------------
    def print_report(self, report_type="qweb"):
        self.ensure_one()
        action = (
                report_type == "xlsx"
                and self.env.ref("npd_tax_report_payment.action_tax_payment_report_xlsx")
                or self.env.ref("npd_tax_report_payment.action_tax_payment_report_pdf")
        )
        return action.report_action(self, config=False)

    def _get_html(self):
        result = {}
        rcontext = {}
        context = dict(self.env.context)
        report = self.browse(context.get("active_id"))
        if report:
            rcontext["o"] = report
            result["html"] = self.env.ref(
                "npd_tax_report_payment.report_tax_payment_report_html"
            )._render(rcontext)
        return result

    @api.model
    def get_html(self, given_context=None):
        return self.with_context(given_context)._get_html()
