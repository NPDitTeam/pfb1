# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
import calendar
import datetime
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    tax_invoice_ids = fields.One2many(
        comodel_name="account.move.tax.invoice",
        inverse_name="move_id",
        readonly=True,
        states={"draft": [("readonly", False)]},
        copy=False,
    )
    payment_id = fields.Many2one('account.payment', string='Payment', readonly=True)

    def _post(self, soft=True):
        """Additional tax invoice info (tax_invoice_number, tax_invoice_date)
        Case sales tax, use Odoo's info, as document is issued out.
        Case purchase tax, use vendor's info to fill back."""
        # Purchase Taxes
        for move in self:
            for tax_invoice in move.tax_invoice_ids.filtered(
                    lambda l: l.tax_line_id.type_tax_use == "purchase"
                              or (
                                      l.move_id.move_type == "entry"
                                      and not l.payment_id
                                      and l.move_id.journal_id.type != "sale"
                              )
            ):
                if (
                        not tax_invoice.tax_invoice_number
                        or not tax_invoice.tax_invoice_date
                ):
                    if tax_invoice.payment_id:  # Defer posting for payment
                        tax_invoice.payment_id.write({"to_clear_tax": True})
                        return self.browse()  # return False
                    elif self.mapped("move_type") == ["entry", "entry"]:
                        # Case Invoice reconcile with Refund, not perfect yet!
                        return self.browse()  # return False
                    else:
                        return self.browse()  # return False
                    #     raise UserError(_("Please fill in tax invoice and tax date"))

        # TOFIX: this operation does cause serious impact in some case.
        # I.e., When a normal invoice with amount 0.0 line, deletion is prohibited,
        #       because it can set back the invoice status of invoice.
        #       Until there is better way to resolve, please keep this commented.
        # Cleanup, delete lines with same account_id and sum(amount) == 0
        # cash_basis_account_ids = (
        #     self.env["account.tax"]
        #     .search([("cash_basis_transition_account_id", "!=", False)])
        #     .mapped("cash_basis_transition_account_id.id")
        # )
        # for move in self:
        #     accounts = move.line_ids.mapped("account_id")
        #     partners = move.line_ids.mapped("partner_id")
        #     for account in accounts:
        #         for partner in partners:
        #             lines = move.line_ids.filtered(
        #                 lambda l: l.account_id == account
        #                 and l.partner_id == partner
        #                 and not l.tax_invoice_ids
        #                 and l.account_id.id not in cash_basis_account_ids
        #             )
        #             if sum(lines.mapped("balance")) == 0:
        #                 lines.unlink()

        res = super()._post(soft)

        # Sales Taxes
        for move in self:
            for tax_invoice in move.tax_invoice_ids.filtered(
                    lambda l: l.tax_line_id.type_tax_use == "sale"
            ):
                try:
                    payment = tax_invoice.payment_id
                    tax_base = 0

                    if payment and payment.invoice_ids:
                        matching_inv_line = payment.invoice_ids[0]

                        if matching_inv_line and matching_inv_line.paid_total > 0:
                            tax_rate = tax_invoice.tax_line_id.amount / 100.0
                            tax_base = matching_inv_line.paid_total / (1.0 + tax_rate)

                            _logger.warning(
                                f"✅ tax_base_amount คำนวณ: {matching_inv_line.paid_total} / (1 + {tax_rate}) = {tax_base}")

                            tinv_number, _ = self._get_tax_invoice_number(
                                move, tax_invoice, tax_invoice.tax_line_id
                            )

                            # ✅ ใช้ payment.date เป็น tax_invoice_date
                            tax_invoice.write({
                                "tax_invoice_number": tinv_number,
                                "tax_invoice_date": payment.date,
                                "tax_base_amount": tax_base,
                                "partner_id": payment.partner_id.id,  # ดึง partner_id จาก payment
                            })
                    else:
                        tinv_number, tinv_date = self._get_tax_invoice_number(
                            move, tax_invoice, tax_invoice.tax_line_id
                        )

                        tax_invoice.write({
                            "tax_invoice_number": tinv_number,
                            "tax_invoice_date": tinv_date,
                            "partner_id": move.partner_id.id,  # ดึง partner_id จาก move
                        })

                except Exception as e:
                    _logger.exception(f"❌ Error updating tax_base_amount for {tax_invoice}: {str(e)}")

        # Check amount tax invoice with move line
        for move in self:
            move.line_ids._checkout_tax_invoice_amount()

        return res