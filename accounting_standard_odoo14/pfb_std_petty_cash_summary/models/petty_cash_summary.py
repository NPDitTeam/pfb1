from re import T
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from functools import partial
from odoo.tools.misc import formatLang, get_lang


class PettyCashExpenseRows(models.Model):
    _name = "petty.cash.summary.rows"
    _description = "Petty Cash Summary"


    petty_cash_id = fields.Many2one("petty.cash", string="Petty Cash")
    expense_name = fields.Char(string="Description")
    user_id = fields.Many2one("res.users", string="User", index=True, default=lambda self: self.env.user)
    date = fields.Date(string="Date", default=fields.Datetime.now)
    total = fields.Float(string="Total")
    company_id = fields.Many2one(
        "res.company",
        "Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    employee_id = fields.Many2one('hr.employee', string='Payee')
    wht_amount = fields.Float(
        string="Wht"
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
    amount = fields.Float(
        string="Amount",
    )
