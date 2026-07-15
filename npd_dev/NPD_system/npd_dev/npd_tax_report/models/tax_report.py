# -*- coding: utf-8 -*-
# NPD TAX Report - native Odoo report backed by a SQL view.
# Source = customer invoices (account.move, move_type = 'out_invoice'), each
# left-joined to its (latest) receipt/payment via the account.payment.invoice
# junction, so invoices without tax still show up with Tax = 0.

from odoo import api, fields, models, tools


class NpdTaxReport(models.Model):
    _name = "npd.tax.report"
    _description = "NPD TAX Report"
    _auto = False
    _order = "invoice_date desc, invoice_number"

    # --- columns coming straight from the SQL view ---
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Cust./Sup.", readonly=True)
    move_id = fields.Many2one("account.move", string="Journal Entry", readonly=True)
    move_branch_id = fields.Many2one("res.branch", string="Branch", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)
    payment_id = fields.Many2one("account.payment", string="Payment Ref", readonly=True)

    invoice_date = fields.Date(string="Date", readonly=True)
    invoice_number = fields.Char(string="Invoice", readonly=True)
    base_amount = fields.Monetary(
        string="Base Amount",
        currency_field="currency_id",
        group_operator="sum",
        readonly=True,
    )
    tax_amount = fields.Monetary(
        string="Tax Amount",
        currency_field="currency_id",
        group_operator="sum",
        readonly=True,
    )

    # --- related columns (read on the fly, not part of the SQL view) ---
    partner_vat = fields.Char(
        string="Tax ID", related="partner_id.vat", readonly=True
    )
    partner_branch = fields.Char(
        string="Branch ID", related="partner_id.branch", readonly=True
    )
    payment_state = fields.Selection(
        string="สถานะการชำระ",
        related="move_id.payment_state",
        readonly=True,
    )

    # --- payment-derived columns.
    # One invoice can be paid by several receipts, so every linked payment is
    # collected and joined with a comma. Computed with getattr so the module
    # never fails to load even though the underlying account.payment fields
    # come from other custom modules.
    payment_name = fields.Char(
        string="Payment", compute="_compute_payment_info", readonly=True
    )
    doc_ref = fields.Char(
        string="Doc Ref.", compute="_compute_payment_info", readonly=True
    )

    @api.depends("move_id")
    def _compute_payment_info(self):
        APInv = self.env["account.payment.invoice"]
        Payment = self.env["account.payment"]
        # Gather every payment linked to each invoice in a single query.
        payments_by_invoice = {}
        move_ids = self.mapped("move_id").ids
        if move_ids:
            for link in APInv.search([("invoice_id", "in", move_ids)]):
                if not link.payment_id:
                    continue
                payments_by_invoice.setdefault(
                    link.invoice_id.id, Payment
                )
                payments_by_invoice[link.invoice_id.id] |= link.payment_id

        for rec in self:
            payments = payments_by_invoice.get(rec.move_id.id, Payment)
            names, refs = [], []
            for payment in payments:
                # Payment = receipt/payment document number (e.g. CUST.IN-...)
                pname = getattr(payment, "name", False)
                if pname and pname not in names:
                    names.append(pname)
                # Doc Ref. = the payment's journal entry move (e.g. RV-...)
                move = getattr(payment, "move_id", False)
                rname = move.name if move else False
                if rname and rname not in refs:
                    refs.append(rname)
            rec.payment_name = ", ".join(names)
            rec.doc_ref = ", ".join(refs)

    def _query(self):
        return """
            SELECT
                m.id AS id,
                m.company_id AS company_id,
                m.partner_id AS partner_id,
                m.id AS move_id,
                m.branch_id AS move_branch_id,
                m.currency_id AS currency_id,
                pil.payment_id AS payment_id,
                m.invoice_date AS invoice_date,
                m.name AS invoice_number,
                m.amount_untaxed AS base_amount,
                m.amount_tax AS tax_amount
            FROM account_move m
            LEFT JOIN LATERAL (
                SELECT pi.payment_id
                FROM account_payment_invoice pi
                WHERE pi.invoice_id = m.id
                  AND pi.payment_id IS NOT NULL
                ORDER BY pi.payment_id DESC
                LIMIT 1
            ) pil ON TRUE
            WHERE m.move_type = 'out_invoice'
              AND m.state = 'posted'
        """

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s)" % (self._table, self._query())
        )
