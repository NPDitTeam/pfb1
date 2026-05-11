

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class AccountMoveTaxInvoice(models.Model):
    _inherit = "account.move.tax.invoice"

    tax_id = fields.Many2one(
        comodel_name="account.tax",
    )

class TaxReport(models.TransientModel):
    _inherit = "report.tax.report"
    
    def _compute_results(self):
        self.ensure_one()
        self._cr.execute(
            """
            select company_id, account_id, partner_id,
                tax_invoice_number, tax_date, name,
                sum(tax_base_amount) tax_base_amount, sum(tax_amount) tax_amount ,tax_id
            from (
            select t.id, t.company_id, ml.account_id, t.partner_id,
              case when ml.parent_state = 'posted' and t.reversing_id is null
                then t.tax_invoice_number else
                t.tax_invoice_number || ' (VOID)' end as tax_invoice_number,
              t.tax_invoice_date as tax_date,
              case when ml.parent_state = 'posted' and t.reversing_id is null
                then t.tax_base_amount else 0.0 end as tax_base_amount,
              case when ml.parent_state = 'posted' and t.reversing_id is null
                then t.balance else 0.0 end as tax_amount,
              case when m.ref is not null
                then m.ref else ml.move_name end as name,
                case when t.tax_id is not null
                then t.tax_id else ml.tax_line_id  end as tax_id
            from account_move_tax_invoice t
              join account_move_line ml on ml.id = t.move_line_id
              join account_move m on m.id = ml.move_id
            where ml.parent_state in ('posted', 'cancel')
              and t.tax_invoice_number is not null
              and ml.account_id in (select distinct account_id
                                    from account_tax_repartition_line
                                    where account_id is not null
                                    and invoice_tax_id in %s or refund_tax_id in %s)
              and t.report_date >= %s and t.report_date <= %s
              and ml.company_id = %s
              and t.reversed_id is null
            ) a
            group by company_id, account_id, partner_id,
                tax_invoice_number, tax_date, name, tax_id
            order by tax_date, tax_invoice_number
        """,
            (
                tuple(self.tax_id.ids),
                tuple(self.tax_id.ids),
                self.date_from,
                self.date_to,
                self.company_id.id,
            ),
        )
        tax_report_results = self._cr.dictfetchall()
        ReportLine = self.env["tax.report.view"]
        self.results = False
        for line in tax_report_results:
            self.results += ReportLine.new(line)