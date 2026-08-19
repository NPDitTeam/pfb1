# -*- coding: utf-8 -*-
# ต่อยอดจาก l10n_th_tax_report (Copyright 2019 Ecosoft Co., Ltd) License AGPL-3.0
"""ไฟล์ xlsx ของ action 'TAX Report Payment XLSX' (print_report(report_type='xlsx'))

ปุ่ม Export Excel บนหน้าจอ wizard ไม่ได้ใช้ไฟล์นี้ -- ปุ่มนั้นสร้างไฟล์เองด้วย
xlsxwriter ใน wizard/tax_payment_report_wizard.py ไฟล์นี้เก็บไว้ให้ action
รายงานแบบ xlsx ของ Odoo ยังทำงานได้เหมือนโมดูลต้นทาง
"""
import logging

from odoo import models

from odoo.addons.report_xlsx_helper.report.report_xlsx_format import (
    FORMATS,
    XLS_HEADERS,
)

_logger = logging.getLogger(__name__)


class ReportTaxPaymentReportXlsx(models.TransientModel):
    _name = "report.npd_tax_report_payment.report_tax_payment_report_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Tax Payment Report Excel"

    def _get_ws_params(self, wb, data, objects):
        tax_template = {
            "01_index": {
                "header": {"value": "#"},
                "data": {"value": self._render("row_pos")},
                "width": 3,
            },
            "02_tax_date": {
                "header": {"value": "Date"},
                "data": {"value": self._render("tax_date")},
                "width": 12,
            },
            "03_invoice": {
                "header": {"value": "Invoice"},
                "data": {"value": self._render("invoice")},
                "width": 18,
            },
            "04_payment": {
                "header": {"value": "Payment"},
                "data": {"value": self._render("payment")},
                "width": 22,
            },
            "05_tax_invoice": {
                "header": {"value": "Number"},
                "data": {"value": self._render("tax_invoice_number")},
                "width": 18,
            },
            "06_partner_name": {
                "header": {"value": "Cust./Sup."},
                "data": {"value": self._render("partner_name")},
                "width": 30,
            },
            "07_partner_vat": {
                "header": {"value": "Tax ID"},
                "data": {"value": self._render("partner_vat")},
                "width": 15,
            },
            "08_partner_branch": {
                "header": {"value": "Branch ID"},
                "data": {"value": self._render("partner_branch")},
                "width": 12,
            },
            "09_payment_amount": {
                "header": {"value": "Payment Amount"},
                "data": {
                    "value": self._render("payment_amount"),
                    "format": FORMATS["format_tcell_amount_right"],
                },
                "width": 21,
            },
            "10_tax_base_amount": {
                "header": {"value": "Base Amount"},
                "data": {
                    "value": self._render("tax_base_amount"),
                    "format": FORMATS["format_tcell_amount_right"],
                },
                "width": 21,
            },
            "11_tax_amount": {
                "header": {"value": "Tax Amount"},
                "data": {
                    "value": self._render("tax_amount"),
                    "format": FORMATS["format_tcell_amount_right"],
                },
                "width": 21,
            },
            "12_doc_ref": {
                "header": {"value": "Doc Ref."},
                "data": {"value": self._render("doc_ref")},
                "width": 18,
            },
            "13_branch_name": {
                "header": {"value": "Branch"},
                "data": {"value": self._render("branch_name")},
                "width": 20,
            },
        }
        ws_params = {
            "ws_name": "TAX Payment Report",
            "generate_ws_method": "_vat_report",
            "title": "TAX Payment Report",
            "wanted_list": [k for k in sorted(tax_template.keys())],
            "col_specs": tax_template,
        }
        if any(tax.type_tax_use == "sale" for tax in objects.tax_id):
            ws_params["ws_name"] = "Sale TAX Payment Report"
            ws_params["title"] = "Sale TAX Payment Report"
        elif any(tax.type_tax_use == "purchase" for tax in objects.tax_id):
            ws_params["ws_name"] = "Purchase TAX Payment Report"
            ws_params["title"] = "Purchase TAX Payment Report"

        return [ws_params]

    def _vat_report(self, wb, ws, ws_params, data, objects):
        ws.set_landscape()
        ws.fit_to_pages(1, 0)
        ws.set_header(XLS_HEADERS["xls_headers"]["standard"])
        ws.set_footer(XLS_HEADERS["xls_footers"]["standard"])
        self._set_column_width(ws, ws_params)
        row_pos = 0
        # title
        row_pos = self._write_ws_title(ws, row_pos, ws_params, True)
        # company data
        ws.write_column(
            row_pos, 1, ["Period :", "Partner :"], FORMATS["format_left_bold"]
        )
        ws.write_column(
            row_pos,
            2,
            [
                (objects.date_range_id.display_name) or "",
                (objects.company_id.display_name) or "",
            ],
        )
        ws.write_column(
            row_pos, 5, ["Tax ID :", "Branch ID :"], FORMATS["format_left_bold"]
        )
        ws.write_column(
            row_pos,
            6,
            [
                (objects.company_id.partner_id.vat) or "",
                (objects.company_id.partner_id.branch) or "",
            ],
        )
        row_pos += 3
        # vat report table
        row_pos = self._write_line(
            ws,
            row_pos,
            ws_params,
            col_specs_section="header",
            default_format=FORMATS["format_theader_blue_left"],
        )
        ws.freeze_panes(row_pos, 0)
        total_payment = 0.00
        total_base = 0.00
        total_tax = 0.00
        for obj in objects:
            for line in obj.results:
                total_payment += line.payment_amount
                total_base += line.tax_base_amount
                total_tax += line.tax_amount

                row_pos = self._write_line(
                    ws,
                    row_pos,
                    ws_params,
                    col_specs_section="data",
                    render_space={
                        "row_pos": row_pos - 5,
                        "tax_date": line.tax_date or "",
                        "invoice": line.invoice_name or "",
                        "payment": line.payment_name or "",
                        "tax_invoice_number": line.tax_invoice_number or "",
                        "partner_name": line.partner_id.display_name or "",
                        "partner_vat": line.partner_id.vat or "",
                        "partner_branch": line.partner_id.branch or "",
                        "payment_amount": line.payment_amount or 0.00,
                        "tax_base_amount": line.tax_base_amount or 0.00,
                        "tax_amount": line.tax_amount or 0.00,
                        "doc_ref": line.name or "",
                        "branch_name": line.branch_name or "",
                    },
                    default_format=FORMATS["format_tcell_left"],
                )
        ws.write_row(
            row_pos,
            8,
            [total_payment, total_base, total_tax],
            FORMATS["format_theader_blue_amount_right"],
        )
