# Copyright 2019 Ecosoft Co., Ltd (https://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models, _


class WithHoldingTaxReportWizard(models.TransientModel):
    _name = "pfb.withholding.tax.report.wizard"
    _description = "Withholding Tax Report Wizard"

    income_tax_form = fields.Selection(
        selection=[
            ("pnd3", "PND3"),
            ("pnd53", "PND53"),
        ],
        string="Income Tax Form",
        required=True,
    )
    # selection = [
    #     ("pnd1", "PND1"),
    #     ("pnd3", "PND3"),
    #     ("pnd3a", "PND3a"),
    #     ("pnd53", "PND53"),
    # ],
    date_range_id = fields.Many2one(
        comodel_name="date.range", string="Date Range", required=True
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        domain=lambda self: self._get_domain_company_id(),
        string="Company",
        required=True,
        ondelete="cascade",
    )

    # is_cheque_payment = fields.Boolean('Cheque Payment')

    def _get_domain_company_id(self):
        selected_companies = self.env["res.company"].browse(
            self._context.get("allowed_company_ids")
        )
        return [("id", "in", selected_companies.ids)]

    def button_export_html(self):
        self.ensure_one()

        date_from = self.date_range_id.date_start
        date_to = self.date_range_id.date_end
        domain = [
            ("cert_id.income_tax_form", "=", self.income_tax_form),
            ("cert_id.date", ">=", date_from),
            ("cert_id.date", "<=", date_to),
            ("cert_id.company_partner_id", "=", self.company_id.partner_id.id),
            ("cert_id.state", "!=", "draft"),
        ]
        return {
            "name": _("ภงด"),
            "type": "ir.actions.act_window",
            "res_model": "withholding.tax.cert.line",
            "view_mode": "tree,form",
            "views": [
                (self.env.ref("pfb_std_withholding_tax_report.withholding_tax_cert_line_tree_view").id, "tree"),
            ],
            "context": self.env.context,
            "domain": domain,
        }