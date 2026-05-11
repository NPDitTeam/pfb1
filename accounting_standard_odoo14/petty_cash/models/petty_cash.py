from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PettyCash(models.Model):
    _name = "petty.cash"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _rec_name = "petty_name"
    _description = "Petty Cash"

    def _get_balance(self):
        for petty in self:
            withdraw = sum(
                line.move_id and line.withdraw_total or 0 for line in petty.withdraw_ids
            )
            expense = sum(
                line.state == "approve" and line.amount_payment or 0
                for line in petty.expense_ids
            )
            petty.balance = withdraw - expense

    def _get_journal_id(self):
        petty_journal_id = self.env.company.petty_journal_id.id
        if petty_journal_id:
            return petty_journal_id

    def _get_account_id(self):
        petty_account_id = self.env.company.petty_account_id.id
        if petty_account_id:
            return petty_account_id

    petty_name = fields.Char(string="Petty Name", required=True)
    journal_id = fields.Many2one(
        "account.journal", index=True, string="Petty Cash Journal", required=True, default=_get_journal_id,
    )
    
    account_id = fields.Many2one(
        "account.account", index=True, string="Petty Cash Account", required=True , 
        domain="[('user_type_id.type', '=', 'liquidity')]", default=_get_account_id
    )
    max_balance = fields.Float(string="Petty Total")
    date = fields.Date(string="Petty Date", default=fields.Datetime.now)
    remark = fields.Text(string="Petty Remark")
    expense_ids = fields.One2many(
        "petty.cash.expense", "petty_cash_id", string="Expense Line"
    )
    withdraw_ids = fields.One2many(
        "petty.cash.withdraw", "petty_cash_id", string="Withdraw"
    )
    state = fields.Selection(
        [("draft", "Draft"), ("process", "Process"), ("cancel", "Cancel")],
        string="State",
        default="draft",
    )
    balance = fields.Float(string="Balance", digits=(64, 2), compute="_get_balance")
    user_id = fields.Many2one(
        "res.users", string="Petty Cash Holder", index=True, 
        default=lambda self: self.env.user
    )
    company_id = fields.Many2one('res.company', 'Company',
        store=True, readonly=True,
        default=lambda self: self.env.company)
    
    def action_confirm(self):
        self.state = "process"

    def action_cancel(self):
        self.state = "cancel"

    def action_redraft(self):
        self.state = "draft"


class PettyCashWithdraw(models.Model):
    _name = "petty.cash.withdraw"
    _order = 'date DESC'

    petty_cash_id = fields.Many2one("petty.cash", string="Petty Cash")
    date = fields.Date(
        string="Withdraw Date", default=fields.Datetime.now, required=True
    )
    desc = fields.Char(string="Withdraw Desc", required=True)
    withdraw_total = fields.Float(
        string="Withdraw Total", digits=(64, 2), required=True
    )
    payment_method_id = fields.Many2one(
        "payment.method", string="Withdraw Method", required=True,      domain="[('is_active','=',True),'|',('company_id', '=', False),('company_id', '=', company_id)]"
    )
    move_id = fields.Many2one("account.move", string="Journal Entry")
    company_id = fields.Many2one('res.company', related='petty_cash_id.company_id', string='Company', store=True, readonly=True)


    def unlink(self):
        if self.move_id:
            raise UserError(_("Can't delete move entry."))
        return super(PettyCashWithdraw, self).unlink()

    def get_sequence(self):
        return self.env["ir.sequence"].next_by_code("petty.payment")
        
    def create_account_move(self):
        vals = []
        account_move = self.env["account.move"]
        if self.withdraw_total == 0:
            raise UserError(_("Please Input Total."))
        if (
            round(self.withdraw_total + self.petty_cash_id.balance,2)
        ) > self.petty_cash_id.max_balance:
            raise UserError(_("Withdraw is not balance"))

        vals.append(
            [
                0,
                0,
                {
                    "account_id": self.petty_cash_id.account_id.id,
                    "debit": self.withdraw_total > 0 and abs(self.withdraw_total) or 0,
                    "credit": self.withdraw_total < 0 and abs(self.withdraw_total) or 0,
                    "name": self.desc,
                    "date": self.date,
                },
            ]
        )

        vals.append(
            [
                0,
                0,
                {
                    "account_id": self.payment_method_id.account_id.id,
                    "debit": self.withdraw_total < 0 and abs(self.withdraw_total) or 0,
                    "credit": self.withdraw_total > 0 and abs(self.withdraw_total) or 0,
                    "name": self.desc,
                    "date": self.date,
                },
            ]
        )
        name = self.get_sequence()#self.env["ir.sequence"].next_by_code("petty.payment")
        move_id = account_move.create(
            {
                "date": self.date,
                "journal_id": self.petty_cash_id.journal_id.id,
                "ref": self.petty_cash_id.petty_name,
                'name': name,
                "line_ids": vals,
            }
        )

        move_id.post()
        self.move_id = move_id
        return True

    @api.onchange("payment_method_id")
    def _onchange_payment_method_id(self):
        if (
            self.petty_cash_id.max_balance != self.petty_cash_id.balance
            and self.petty_cash_id.max_balance > 0
        ):
            self.withdraw_total = (
                self.petty_cash_id.max_balance - self.petty_cash_id.balance
            )

    def action_approve(self):
        self.create_account_move()
        return True

class ResCompany(models.Model):
    _inherit = "res.company"

    petty_journal_id = fields.Many2one(
        "account.journal", index=True, string="Petty Cash Journal", required=False
    )
    petty_account_id = fields.Many2one(
        "account.account", index=True, string="Petty Cash Account", required=False
    )

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    petty_journal_id = fields.Many2one(
        comodel_name="account.journal",
        related="company_id.petty_journal_id",
        string="Petty Cash Journal",
        readonly=False,
    )
    petty_account_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.petty_account_id",
        string="Petty Cash Account",
        readonly=False,
    )