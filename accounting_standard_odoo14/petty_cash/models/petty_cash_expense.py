from re import T
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from functools import partial
from odoo.tools.misc import formatLang, get_lang


class PettyCashExpense(models.Model):
    _name = "petty.cash.expense"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _description = "Petty Cash Expense"
    _rec_name = "expense_name"
    _order = "expense_name desc"

    @api.depends("expense_line.price_total","wht_line.tax_amount")
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = amount_wht = 0.0
            for line in order.expense_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            for wht in order.wht_line:
                amount_wht += wht.tax_amount
            amount_total = amount_untaxed + amount_tax
            order.update(
                {
                    "amount_untaxed": amount_untaxed,
                    "amount_tax": amount_tax,
                    "amount_total": amount_untaxed + amount_tax,
                    "amount_wht": amount_wht,
                    "amount_payment": amount_total - amount_wht,
                }
            )

    petty_cash_id = fields.Many2one("petty.cash", string="Petty Cash")
    user_id = fields.Many2one(
        "res.users", string="User", index=True, default=lambda self: self.env.user
    )
    employee_id = fields.Many2one('hr.employee', string='Payee')
    expense_name = fields.Char(string="Description")
    date = fields.Date(string="Date", default=fields.Datetime.now)
    total = fields.Float(string="Total")
    expense_line = fields.One2many("expense.line", "petty_expense_id", string="Desc")
    company_id = fields.Many2one(
        "res.company",
        "Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        store=True,
        readonly=True,
        tracking=True,
        required=True,
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        store=True,
        readonly=True,
        compute="_amount_all",
        tracking=5,
    )
    amount_tax = fields.Monetary(
        string="Taxes", store=True, readonly=True, compute="_amount_all"
    )
    amount_total = fields.Monetary(
        string="Total", store=True, readonly=True, compute="_amount_all", tracking=4
    )
    amount_wht = fields.Monetary(
        string="Wht", store=True, readonly=True, compute="_amount_all"
    )
    amount_payment = fields.Monetary(
        string="Payment Amount", store=True, readonly=True, compute="_amount_all"
    )

    note = fields.Text(string="Note")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("process", "Process"),
            ("approve", "Approve"),
            ("reject", "Reject"),
            ("cancel", "Cancel"),
        ],
        string="State",
        default="draft",
    )
    move_id = fields.Many2one("account.move", string="Journal Entry")
    tax_line = fields.One2many(
        "petty.expense.line.tax", "petty_expense_id", string="Tax"
    )
    wht_line = fields.One2many('withholding.tax.cert', 'petty_expense_id', string='WHT Line')
    amount = fields.Monetary(
        string="Amount",
        store=True,
        readonly=False,
        tracking=5,
    )
    @api.model_create_multi
    def create(self, vals_list):
        cash_exp = super().create(vals_list)
        for exp in cash_exp:
            exp.compute_line_tax()
        return cash_exp

    def write(self, vals):
        cash_exp = super().write(vals)
        for exp in self:
            # Check expense line change qty price or tax to computetax
            reset_compute_tax = False
            for line in exp.expense_line:
                if line.is_compute_tax == True:
                    reset_compute_tax = line.is_compute_tax
                line.is_compute_tax = False
            if reset_compute_tax == True:
                exp.tax_line.unlink()
                exp.compute_line_tax()
        return cash_exp

    # def compute_tax(self):
    #     tes = {}
    #     for exp in self:
    #         for line in exp.expense_line:
    #             price_reduce = line.price_unit  # * (1.0 - line.discount / 100.0)
    #             taxes = line.tax_id.compute_all(
    #                 price_reduce, quantity=line.product_uom_qty, product=line.product_id
    #             )["taxes"]
    #             for tax in line.tax_id:
    #                 tes.setdefault(
    #                     tax.id, {"amount": 0.0, "base": 0.0, "account_id": ""}
    #                 )
    #                 for t in taxes:
    #                     tax_repartition_line = self.env[
    #                         "account.tax.repartition.line"
    #                     ].browse(t["tax_repartition_line_id"])
    #                     account_id = tax_repartition_line.account_id.id or None
    #                     tes[tax.id]["account_id"] = account_id
    #                     tes[tax.id]["amount"] += t["amount"]
    #                     tes[tax.id]["base"] += t["base"]
    #         for group in tes:
    #             self.env["petty.expense.line.tax"].create(
    #                 {
    #                     "petty_expense_id": exp.id,
    #                     "tax_id": group,
    #                     "account_id": tes[group]["account_id"],
    #                     "balance": tes[group]["amount"],
    #                     "tax_base_amount": tes[group]["base"],
    #                 }
    #             )
    #     return True

    def compute_line_tax(self):
        for exp in self:
            for line in exp.expense_line:
                price_reduce = line.price_unit  # * (1.0 - line.discount / 100.0)
                taxes = line.tax_id.compute_all(
                    price_reduce, quantity=line.product_uom_qty, product=line.product_id
                )["taxes"]
                for tax in line.tax_id:
                    for t in taxes:
                        tax_repartition_line = self.env["account.tax.repartition.line"].browse(t["tax_repartition_line_id"])
                        account_id = tax_repartition_line.account_id.id or None
                        self.env["petty.expense.line.tax"].create(
                            {
                                "petty_expense_id": exp.id,
                                "tax_id": tax.id,
                                "account_id": account_id,
                                "balance": t["amount"],
                                "tax_base_amount": t["base"],
                                "tax_repartition_line_id":t['tax_repartition_line_id'],
                            }
                        )

        return True

    def action_confirm(self):
        self.state = "process"

    def action_approve(self):
        check_balance = self.petty_cash_id.balance - self.amount_total
        if check_balance < 0:
            raise ValidationError(
                _("Petty Cash is balance not enough please check petty cash")
            )
        if not self.move_id:
            self.move_id = self.create_move()
        self.state = "approve"

    def action_reject(self):
        self.state = "reject"

    def action_cancel(self):
        if self.move_id:
            self.move_id.button_cancel()
            self.move_id.unlink()
        self.state = "cancel"

    def create_move(self):
        vals = []
        account_move = self.env["account.move"]
        sub_total = 0
        name = self.env["ir.sequence"].next_by_code("petty.expense")
        move_id = account_move.create(
            {
                "date": self.date,
                "journal_id": self.petty_cash_id.journal_id.id,
                "ref": name,
                "name": name,
            }
        )
        self.env['account.move.line'].with_context(check_move_validity=False).create(
                {
                    "account_id": self.petty_cash_id.account_id.id,
                    "debit": 0,
                    "credit": self.amount_payment,
                    "name": self.expense_name,
                    "date": self.date,
                    "move_id": move_id.id
                },
        )
        for wt in self.wht_line:
            if not wt.account_id:
                raise UserError(_("Please config account withholding tax in configuration"))
            self.env['account.move.line'].with_context(check_move_validity=False).create(
                    {
                        "account_id": wt.account_id.id,
                        "debit": 0,
                        "partner_id": wt.supplier_partner_id.id,
                        "credit": wt.tax_amount,
                        "name": _("Withholding Tax"),
                        "date": wt.date,
                        "move_id": move_id.id
                    }

            )

        for line in self.expense_line:
            sub_total += line.price_subtotal
            self.env['account.move.line'].with_context(check_move_validity=False).create(
                    {
                        "account_id": line.account_id.id,
                        "debit": line.price_subtotal > 0.0 and line.price_subtotal or 0.0,
                        "credit": line.price_subtotal < 0.0 and abs(line.price_subtotal) or 0.0,
                        "name": line.name or _("Petty Cash ") + self.user_id.name,
                        "date": self.date,
                        "move_id": move_id.id,
                        "analytic_account_id": line.analytic_account_id.id or None,
                        "analytic_tag_ids":[(6, 0, line.analytic_tag_ids.ids)] or None,
                    },
            )
        tax_total = 0
        for vat in self.tax_line:
            tax_total += vat.balance
            if vat.invoice_ref == "" or not vat.date_invoice or not vat.partner_id:
                raise ValidationError(_("Please Input Invoice Ref Invoice Date and Partner ID"))
            move_line_id = self.env['account.move.line'].with_context(check_move_validity=False).create({
                        "account_id": vat.account_id.id,
                        "debit": vat.balance,
                        "partner_id": vat.partner_id.id,
                        "credit": 0.0,
                        "name": _("Vat Petty Cash Ref:%s")%(vat.invoice_ref or ""),
                        "date": self.date,
                        "move_id": move_id.id,
            })
            self._create_tax_move(vat.invoice_ref,vat.date_invoice,vat.partner_id, move_id.id,move_line_id,vat.tax_id.id,vat.tax_base_amount,vat.balance)
            move_line_id.update({'tax_repartition_line_id': vat.tax_repartition_line_id.id})

        move_id.post()
        self.expense_name = name
        return move_id

    def _create_tax_move(self, invoice_name,invoice_date,partner_id,move_id, move_line_id, tax_line_id, tax_base=0.00, tax_amount=0.00):
        TaxInvoice = self.env["account.move.tax.invoice"]
        TaxInvoice.create(
            {"move_id": move_id,
             "move_line_id": move_line_id.id,
             "partner_id": partner_id.id,
             "tax_invoice_number": invoice_name,
             "tax_invoice_date": invoice_date,
             "tax_base_amount": abs(tax_base),
             "balance": abs(tax_amount),
             'tax_line_id': tax_line_id,
             })
           


class ExpenseLine(models.Model):
    _name = "expense.line"

    @api.depends("product_uom_qty", "price_unit", "tax_id")
    def _compute_amount(self):
        for line in self:
            price = line.price_unit  # * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(
                price,
                line.petty_expense_id.currency_id,
                line.product_uom_qty,
                product=line.product_id,
            )
            line.update(
                {
                    "price_tax": sum(
                        t.get("amount", 0.0) for t in taxes.get("taxes", [])
                    ),
                    "price_total": taxes["total_included"],
                    "price_subtotal": taxes["total_excluded"],
                }
            )
            if self.env.context.get(
                "import_file", False
            ) and not self.env.user.user_has_groups("account.group_account_manager"):
                line.tax_id.invalidate_cache(
                    ["invoice_repartition_line_ids"], [line.tax_id.id]
                )

    petty_expense_id = fields.Many2one(
        comodel_name="petty.cash.expense",
        string="Petty Payment",
        required=False,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=False,
    )
    account_id = fields.Many2one(
        "account.account",
        string="Account",
        index=True,
        ondelete="cascade",
        tracking=True,
    )
    unit_price = fields.Float(string="Unit Price", required=False, digits=(64, 2))
    product_uom_qty = fields.Float(
        string="Quantity", digits="Product Unit of Measure", required=True, default=1.0
    )
    tax_id = fields.Many2many(
        "account.tax",
        string="Taxes",
        domain=["|", ("active", "=", False), ("active", "=", True)],
    )
    price_unit = fields.Float(
        "Unit Price", required=True, digits="Product Price", default=0.0
    )
    price_subtotal = fields.Monetary(
        compute="_compute_amount", stribalanceng="Subtotal", readonly=True, store=True
    )
    price_tax = fields.Float(
        compute="_compute_amount", string="Total Tax", readonly=True, store=True
    )
    price_total = fields.Monetary(
        compute="_compute_amount", string="Total", readonly=True, store=True
    )
    currency_id = fields.Many2one(
        related="petty_expense_id.currency_id",
        depends=["petty_expense_id.currency_id"],
        store=True,
        string="Currency",
        readonly=True,
    )
    name = fields.Text(
        string="Description",
        required=False,
    )
    is_compute_tax = fields.Boolean(string="Compute Tax", default=False)
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
    )
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')


    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            line.name = line.product_id.name
            line.account_id = line.product_id.property_account_expense_id
            line.tax_id = line.product_id.supplier_taxes_id.ids

    @api.onchange("product_uom_qty", "tax_id", "price_unit")
    def _onchange_product_uom(self):
        self.is_compute_tax = True


class PettyExpenseLineTax(models.Model):
    _name = "petty.expense.line.tax"

    petty_expense_id = fields.Many2one(
        comodel_name="petty.cash.expense",
        string="Petty Payment",
        required=False,
        ondelete="cascade",
    )
    tax_id = fields.Many2one(
        "account.tax",
        string="Taxes",
        domain=["|", ("active", "=", False), ("active", "=", True)],
    )
    account_id = fields.Many2one(
        "account.account", index=True, string="Account", required=False
    )
    company_id = fields.Many2one(
        comodel_name="res.company", related="petty_expense_id.company_id", store=True
    )
    company_currency_id = fields.Many2one(
        comodel_name="res.currency", related="company_id.currency_id"
    )
    tax_base_amount = fields.Monetary(
        string="Tax Base", currency_field="company_currency_id", copy=False
    )
    balance = fields.Monetary(
        string="Tax Amount", currency_field="company_currency_id", copy=False
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=False,
    )
    invoice_ref = fields.Char(
        string="Invoice Reference",
        required=False,
    )
    date_invoice = fields.Date(
        string="Invoice Date", required=False
    )
    tax_repartition_line_id = fields.Many2one(
        comodel_name="account.tax.repartition.line",
    )


class WithholdingTaxCert(models.Model):
    _inherit = "withholding.tax.cert"

    petty_expense_id = fields.Many2one('petty.cash.expense', string='Petty Cash Expense')