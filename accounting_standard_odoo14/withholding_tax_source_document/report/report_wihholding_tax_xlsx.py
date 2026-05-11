# Copyright 2019 Ecosoft Co., Ltd (https://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import models

from odoo.addons.report_xlsx_helper.report.report_xlsx_format import (
    FORMATS,
    XLS_HEADERS,
)


class WithholdingTaxReportXslx(models.AbstractModel):
    _inherit = "report.withholding.tax.report.xlsx"

    def _get_ws_params(self, wb, data, obj):
        withholding_tax_template = {
            "01_sequence": {
                "header": {"value": "No."},
                "data": {
                    "value": self._render("sequence"),
                    "format": FORMATS["format_tcell_center"],
                },
                "width": 3,
            },
            "02_vat": {
                "header": {"value": "Tax Invoice"},
                "data": {
                    "value": self._render("vat"),
                    "format": FORMATS["format_tcell_center"],
                },
                "width": 16,
            },
            "03_display_name": {
                "header": {"value": "Cus./Sup."},
                "data": {"value": self._render("display_name")},
                "width": 18,
            },
            "04_street": {
                "header": {"value": "Address"},
                "data": {"value": self._render("street")},
                "width": 20,
            },
            "05_date": {
                "header": {"value": "Date"},
                "data": {
                    "value": self._render("date"),
                    "type": "datetime",
                    "format": FORMATS["format_date_dmy_right"],
                },
                "width": 10,
            },
            "06_income_desc": {
                "header": {"value": "Income Description"},
                "data": {"value": self._render("income_desc")},
                "width": 18,
            },
            "07_tax": {
                "header": {"value": "Tax"},
                "data": {
                    "value": self._render("tax"),
                    "type": "number",
                    "format": FORMATS["format_tcell_percent_conditional_right"],
                },
                "width": 8,
            },
            "08_base_amount": {
                "header": {"value": "Base Amount"},
                "data": {
                    "value": self._render("base_amount"),
                    "type": "number",
                    "format": FORMATS["format_tcell_amount_right"],
                },
                "width": 13,
            },
            "09_tax_amount": {
                "header": {"value": "Tax Amount"},
                "data": {
                    "value": self._render("tax_amount"),
                    "type": "number",
                    "format": FORMATS["format_tcell_amount_right"],
                },
                "width": 13,
            },
            "10_tax_payer": {
                "header": {"value": "Tax Payer"},
                "data": {
                    "value": self._render("tax_payer"),
                    "format": FORMATS["format_tcell_center"],
                },
                "width": 12,
            },
            "11_payment_id": {
                "header": {"value": "Doc Ref."},
                "data": {"value": self._render("payment_id")},
                "width": 19,
            },
             "12_source_document": {
                "header": {"value": "Source Document."},
                "data": {"value": self._render("source_document")},
                "width": 19,
            },
        }

        ws_params = {
            "ws_name": "Withholding Tax Report",
            "generate_ws_method": "_withholding_tax_report",
            "title": "Withholding Tax Report - %s" % (obj.company_id.name),
            "wanted_list": [x for x in sorted(withholding_tax_template.keys())],
            "col_specs": withholding_tax_template,
        }

        return [ws_params]

    def _write_ws_lines(self, row_pos, ws, ws_params, obj):
        row_pos = self._write_line(
            ws,
            row_pos,
            ws_params,
            col_specs_section="header",
            default_format=FORMATS["format_theader_blue_center"],
        )
        ws.freeze_panes(row_pos, 0)
        index = 1
        for line in obj.results:
            cancel = line.cert_id.state == "cancel"
            row_pos = self._write_line(
                ws,
                row_pos,
                ws_params,
                col_specs_section="data",
                render_space={
                    "sequence": index,
                    "vat": line.cert_id.supplier_partner_id.vat or "",
                    "display_name": not cancel
                    and line.cert_id.supplier_partner_id.display_name
                    or "Cancelled",
                    "street": not cancel
                    and "{} {} {} {} {}".format(line.cert_id.supplier_partner_id.street or "",
                                          line.cert_id.supplier_partner_id.street2 or "",
                                          line.cert_id.supplier_partner_id.city or "",
                                          line.cert_id.supplier_partner_id.state_id.name or "",
                                          line.cert_id.supplier_partner_id.zip or "")
                    or "",
                    "date": line.cert_id.date,
                    "income_desc": line.wt_cert_income_desc or "",
                    "tax": line.wt_percent / 100 or 0.00,
                    "base_amount": not cancel and line.base or 0.00,
                    "tax_amount": not cancel and line.amount or 0.00,
                    "tax_payer": line.cert_id.tax_payer,
                    "payment_id": line.cert_id.name,
                    "source_document": line.cert_id.source_document,
                },
                default_format=FORMATS["format_tcell_left"],
            )
            index += 1
        return row_pos
