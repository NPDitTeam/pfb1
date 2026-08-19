# -*- coding: utf-8 -*-
# ต่อยอดจาก l10n_th_tax_report (Copyright 2019 Ecosoft Co., Ltd) License AGPL-3.0
"""หน้าจอเลือกเงื่อนไขของรายงาน Thai Tax Reports Payment

ต่างจากของเดิม (l10n_th_tax_report) ตรงที่:
  - เปิดหน้าจอมา Tax Group ตั้ง 'VAT 7%' และ Tax ตั้ง 'ภาษีขาย Vat 7%' ให้เลย
  - ข้อมูลที่ออกรายงานมาจาก account.payment ไม่ใช่ใบแจ้งหนี้
    (ดูรายละเอียดที่ reports/tax_payment_report.py)
"""
import base64
import io
import logging

import xlsxwriter

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# ชื่อที่ใช้ค้นค่าเริ่มต้น -- ถ้า DB ไหนตั้งชื่อไม่ตรง จะ fallback ไปหาตัวแรก
# ที่เป็นภาษีขายในกลุ่มนั้นแทน
DEFAULT_TAX_GROUP_NAME = u"VAT 7%"
DEFAULT_TAX_NAME = u"ภาษีขาย Vat 7%"

# ความกว้างคอลัมน์ของไฟล์ Excel เรียงตามหัวตาราง
#   # / Date / Invoice / Payment / Number / Cust./Sup. / Tax ID / Branch ID /
#   Payment Amount / Base Amount / Tax Amount / Doc Ref. / Branch
COLUMN_WIDTHS = [
    (0, 0, 5),      # #
    (1, 1, 12),     # Date
    (2, 2, 18),     # Invoice
    (3, 3, 22),     # Payment
    (4, 4, 18),     # Number
    (5, 5, 36),     # Cust./Sup. (ชื่อบริษัทยาวสุดในตาราง)
    (6, 6, 17),     # Tax ID
    (7, 7, 11),     # Branch ID
    (8, 10, 16),    # Payment Amount / Base Amount / Tax Amount
    (11, 11, 24),   # Doc Ref.
    (12, 12, 18),   # Branch
]


class TaxPaymentReportWizard(models.TransientModel):
    _name = "tax.payment.report.wizard"
    _description = "Wizard for Tax Payment Report"

    # ------------------------------------------------------------------
    # ค่าเริ่มต้น: VAT 7% / ภาษีขาย Vat 7%
    # ------------------------------------------------------------------
    @api.model
    def _default_tax_group(self):
        group = self.env.ref("l10n_th_pfb.tax_group_vat_7", raise_if_not_found=False)
        if not group:
            group = self.env["account.tax.group"].search(
                [("name", "=", DEFAULT_TAX_GROUP_NAME)], limit=1)
        return group

    @api.model
    def _default_tax_ids(self):
        group = self._default_tax_group()
        if not group:
            return False
        Tax = self.env["account.tax"]
        domain = [
            ("tax_group_id", "=", group.id),
            ("type_tax_use", "=", "sale"),
            ("active", "=", True),
        ]
        tax = (Tax.search(domain + [("name", "=", DEFAULT_TAX_NAME)], limit=1)
               or Tax.search(domain, limit=1))
        return [(6, 0, tax.ids)] if tax else False

    # Search Criteria
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        string="Company",
        required=True,
        ondelete="cascade",
    )
    tax_group_id = fields.Many2one(
        comodel_name="account.tax.group",
        string="Tax Group",
        required=True,
        default=lambda self: self._default_tax_group(),
    )
    tax_id = fields.Many2many(comodel_name="account.tax",
                              required=True,
                              default=lambda self: self._default_tax_ids(), )

    date_range_id = fields.Many2one(
        comodel_name="date.range", string="Period", required=True
    )
    branch_id = fields.Many2one('res.branch', string='Branch')

    # New fields for storing generated report data temporarily
    report_file = fields.Binary(string="Report File", readonly=True)
    report_file_name = fields.Char(string="Report File Name")

    @api.onchange('tax_group_id')
    def _set_tex_id(self):
        """เปลี่ยนกลุ่มภาษี -> เติมภาษีในกลุ่มนั้นให้

        รายงานนี้เป็นรายงานภาษีขาย ถ้ากลุ่มที่เลือกมีภาษีขายอยู่จะเอาเฉพาะ
        ภาษีขาย ถ้าไม่มีเลยค่อยเอาทั้งกลุ่ม (ยังเลือกเพิ่ม/ลบเองได้อยู่)
        """
        for rec in self:
            rec.tax_id = False
            if rec.tax_group_id:
                Tax = rec.env['account.tax']
                domain = [('tax_group_id', '=', rec.tax_group_id.id),
                          ('active', '=', True)]
                tax = Tax.search(domain + [('type_tax_use', '=', 'sale')]) \
                    or Tax.search(domain)
                if tax:
                    rec.write({'tax_id': [(6, 0, tax.ids)]})

    def button_export_html(self):

        action = self.env.ref(
            "npd_tax_report_payment.action_report_tax_payment_report_html")
        vals = action.read()[0]
        context1 = vals.get("context", {})
        if context1:
            context1 = safe_eval(context1)

        model = self.env["report.tax.payment.report"]
        report = model.create(self._prepare_tax_report())

        context1["active_id"] = report.id
        context1["active_ids"] = [report.id]
        context1["active_model"] = "report.tax.payment.report"
        context1["branch_id"] = report.branch_id.id or False

        # ส่งค่าของ wizard ไปด้วย เผื่อปุ่ม Export บนหน้ารายงานต้องสร้าง wizard ใหม่
        context1["wizard_company_id"] = self.company_id.id
        context1["wizard_tax_group_id"] = self.tax_group_id.id
        context1["wizard_tax_id"] = self.tax_id.ids
        context1["wizard_date_range_id"] = self.date_range_id.id
        context1["wizard_branch_id"] = self.branch_id.id

        vals["context"] = context1
        return vals

    def button_export_pdf(self):

        report_type = "qweb-pdf"
        return self._export(report_type)

    def _generate_excel_report(self, is_test_report=False):
        """สร้างไฟล์ xlsx ด้วย xlsxwriter (ใช้ร่วมกันทั้งปุ่ม Export ปกติ/Test)"""
        _logger.info("Starting _generate_excel_report. Is test report: %s",
                     is_test_report)
        report_values = self._prepare_tax_report()

        output = io.BytesIO()
        try:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})

            sheet_name = ('Tax Payment Report Test' if is_test_report
                          else 'Tax Payment Report')
            sheet = workbook.add_worksheet(sheet_name)

            text_format = workbook.add_format({'align': 'left'})
            currency_format = workbook.add_format(
                {'num_format': '#,##0.00', 'align': 'right'})
            header_format = workbook.add_format(
                {'bold': True, 'align': 'center', 'bg_color': '#D3D3D3'})

            # ความกว้างคอลัมน์ (คอลัมน์, คอลัมน์, กว้าง) -- ไม่ตั้งไว้ Excel จะใช้
            # ความกว้างมาตรฐาน 8.43 ตัวเลขยาว ๆ เลยขึ้นเป็น ###### และชื่อลูกค้าโดนบัง
            for first_col, last_col, width in COLUMN_WIDTHS:
                sheet.set_column(first_col, last_col, width)

            row = 0
            col = 0

            # Title
            report_title = "VAT Report (Payment)"
            if report_values.get('tax_id'):
                taxes = self.env['account.tax'].browse(report_values['tax_id'])
                if taxes:
                    tax_use = taxes[0].type_tax_use
                    if tax_use == 'sale':
                        report_title = "Sale VAT Report (Payment)"
                    elif tax_use == 'purchase':
                        report_title = "Purchase VAT Report (Payment)"

            if is_test_report:
                report_title = "Test " + report_title

            sheet.merge_range(
                row, 0, row, 12, report_title,
                workbook.add_format(
                    {'bold': True, 'align': 'center', 'font_size': 14}))
            row += 2

            # Filters
            sheet.write(row, col, 'Period', header_format)
            sheet.write(row, col + 1, 'Partner', header_format)
            sheet.write(row, col + 2, 'Tax ID', header_format)
            sheet.write(row, col + 3, 'Branch ID', header_format)
            row += 1

            date_range = self.env['date.range'].browse(
                report_values.get('date_range_id'))
            company = self.env['res.company'].browse(
                report_values.get('company_id'))
            company_partner = company.partner_id

            sheet.write(row, col, date_range.display_name or '', text_format)
            sheet.write(row, col + 1, company.display_name or '', text_format)
            sheet.write(row, col + 2, company_partner.vat or '', text_format)
            sheet.write(row, col + 3, company_partner.branch or '', text_format)
            row += 2

            # Detailed Report Data
            # create() สร้างบรรทัดให้เสร็จในตัวแล้ว (ดู reports/tax_payment_report.py)
            report_obj = self.env["report.tax.payment.report"].create(report_values)
            results_lines = report_obj.results
            _logger.info("Number of result lines: %s", len(results_lines))

            for tax in self.env['account.tax'].browse(report_values['tax_id']):
                sheet.write(row, col, '', text_format)
                sheet.merge_range(
                    row, col + 1, row, col + 12, tax.name,
                    workbook.add_format(
                        {'bold': True, 'align': 'left', 'font_size': 12}))
                row += 1

                # Header Line for details
                sheet.write(row, col, '#', header_format)
                sheet.write(row, col + 1, 'Date', header_format)
                sheet.write(row, col + 2, 'Invoice', header_format)
                sheet.write(row, col + 3, 'Payment', header_format)
                sheet.write(row, col + 4, 'Number', header_format)
                sheet.write(row, col + 5, 'Cust./Sup.', header_format)
                sheet.write(row, col + 6, 'Tax ID', header_format)
                sheet.write(row, col + 7, 'Branch ID', header_format)
                sheet.write(row, col + 8, 'Payment Amount', header_format)
                sheet.write(row, col + 9, 'Base Amount', header_format)
                sheet.write(row, col + 10, 'Tax Amount', header_format)
                sheet.write(row, col + 11, 'Doc Ref.', header_format)
                sheet.write(row, col + 12, 'Branch', header_format)
                row += 1
                sheet.freeze_panes(row, 0)

                line_num = 1
                total_payment = 0.0
                total_base = 0.0
                total_tax = 0.0

                for line in results_lines:
                    if line.tax_id.id != tax.id:
                        continue
                    sheet.write(row, col, line_num, text_format)
                    sheet.write(row, col + 1, line.tax_date or '', text_format)
                    sheet.write(row, col + 2, line.invoice_name or '', text_format)
                    sheet.write(row, col + 3, line.payment_name or '', text_format)
                    sheet.write(row, col + 4, line.tax_invoice_number or '',
                                text_format)
                    sheet.write(row, col + 5, line.partner_id.display_name or '',
                                text_format)
                    sheet.write(row, col + 6, line.partner_id.vat or '', text_format)
                    sheet.write(row, col + 7, line.partner_id.branch or '',
                                text_format)
                    sheet.write(row, col + 8, line.payment_amount, currency_format)
                    sheet.write(row, col + 9, line.tax_base_amount, currency_format)
                    sheet.write(row, col + 10, line.tax_amount, currency_format)
                    sheet.write(row, col + 11, line.name or '', text_format)
                    sheet.write(row, col + 12, line.branch_name or '', text_format)

                    line_num += 1
                    total_payment += line.payment_amount
                    total_base += line.tax_base_amount
                    total_tax += line.tax_amount
                    row += 1

                # Total Line
                sheet.write(row, col + 7, 'Total:', header_format)
                sheet.write(row, col + 8, total_payment, currency_format)
                sheet.write(row, col + 9, total_base, currency_format)
                sheet.write(row, col + 10, total_tax, currency_format)
                row += 2

            workbook.close()
            output.seek(0)
            return output.read()

        except Exception as e:
            _logger.error("Error creating Excel report: %s", e, exc_info=True)
            raise

    def _get_report_action(self, is_test_report=False):
        """สร้างไฟล์แล้วส่ง action ให้เบราว์เซอร์โหลดผ่าน /web/content"""
        xlsx_data = self._generate_excel_report(is_test_report=is_test_report)
        report_name = 'Tax Payment Report{} - {}.xlsx'.format(
            ' Test' if is_test_report else '',
            # ชื่อ period เป็น 07/2026 -- ต้องเปลี่ยน / เป็น - ไม่งั้นตอนดาวน์โหลด
            # เบราว์เซอร์อ่านเป็นเส้นทางโฟลเดอร์ ชื่อไฟล์จะเหลือแค่ 2026.xlsx
            (self.date_range_id.display_name or '').replace(' ', '_').replace('/', '-')
        )

        self.write({
            'report_file': base64.b64encode(xlsx_data),
            'report_file_name': report_name,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/{}/{}/{}'.format(
                self._name, self.id, 'report_file'
            ),
            'target': 'new',
        }

    def button_export_xlsx(self):
        return self._get_report_action(is_test_report=False)

    def button_export_test_xlsx(self):
        return self._get_report_action(is_test_report=True)

    def _prepare_tax_report(self):
        return {
            "company_id": self.company_id.id,
            "tax_id": self.tax_id.ids,
            "date_range_id": self.date_range_id.id,
            "date_from": self.date_range_id.date_start,
            "date_to": self.date_range_id.date_end,
            "branch_id": self.branch_id.id,
        }

    def _export(self, report_type):
        model = self.env["report.tax.payment.report"]
        report = model.create(self._prepare_tax_report())
        return report.print_report(report_type)
