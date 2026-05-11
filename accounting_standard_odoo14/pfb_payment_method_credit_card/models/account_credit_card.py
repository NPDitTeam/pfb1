from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

class AccountPaymentMethod(models.Model):
    _inherit = "payment.method"

    type = fields.Selection(
        [('cash', 'Cash'),
         ('cheque', 'Cheque'),
         ('bank', 'Bank'),
         ('discount', 'Discount'),
         ('ap', 'AP'),
         ('ar', 'AR'),
         ('other', 'Other'),
         ('creditcard', 'Credit Card')
         ],
        'Payment method',
        required=True
    )
class AccountPaidLine(models.Model):
    _inherit = "account.paid.line"
    credit_card_id = fields.Many2one("account.credit.card", string="Credit Card",
                                     domain="[('state', '=', 'draft')]")

class AccountVoucherPayment(models.Model):
    _inherit = 'account.voucher.payment'
    credit_card_id = fields.Many2one("account.credit.card", string="Credit Card",
                                     domain="[('state', '=', 'draft')]")

class AccountVoucher(models.Model):
    _inherit = 'account.voucher'
    credit_card_id = fields.Many2one("account.credit.card", string="Credit Card",
                                     domain="[('state', '=', 'draft')]")
class AccountVoucherPayment(models.Model):
    _inherit = 'account.voucher.payment'
    credit_card_id = fields.Many2one("account.credit.card", string="Credit Card",
                                     domain="[('state', '=', 'draft')]")


class AccountPayment(models.Model):
    _inherit = "account.payment"
    
    payment_method_one_id = fields.Many2one("payment.method",
                                            string="Payment Method",
                                            domain="[('type', 'in', ['cash','bank','cheque','creditcard']),('is_active','=',True)]")
    credit_card_id = fields.Many2one("account.credit.card", string="Credit Card",
                                domain="[('state', '=', 'draft')]")
class AccountPaymentInvoice(models.Model):
    _inherit = "account.payment.invoice"
    
    payment_method_one_id = fields.Many2one("payment.method",
                                            string="Payment Method",
                                            domain="[('type', 'in', ['cash','bank','cheque','creditcard']),('is_active','=',True)]")
    credit_card_id = fields.Many2one("account.credit.card", string="Credit Card",
                                domain="[('state', '=', 'draft')]")
class AccountCheque(models.Model):
    _name = "account.credit.card"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _description = "credit_card payment and receipt"
    _order = 'date_done DESC'

    name = fields.Char(string="Credit Card Number", required=True)
    # date_credit_card = fields.Date(
    #     string="Date Credit Card", required=True, default=fields.Datetime.now
    # )
    date_done = fields.Date(string="Date Credit Card")
    # date_receipt = fields.Date(string="Date Credit Card Receipt")
    credit_card_type = fields.Selection(
        [
            ("outbound", "Payment Credit Card"),
            ("inbound", "Receipt Credit Card"),
        ],
        string="Type",
        default="inbound",
        required=True,
    )
    credit_card_total = fields.Float(string="Credit Card Total", digits=(24, 2), required=True)
    remark = fields.Text(string="Note")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ('assigned','Assigned'),
            ('reject','Reject'),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        string="Status",
        default="draft",
    )
    partner_id = fields.Many2one("res.partner", string="Partner")
    bank_partner_id = fields.Many2one(
        "res.partner.bank", string="Bank Account Transfer"
    )
    # bank_id = fields.Many2one("res.bank", string="Bank")
    move_id = fields.Many2one("account.move", string="Move Entry")

    account_bank_id = fields.Many2one("account.account", string="Account Bank", domain="[('user_type_id.type', '=', 'liquidity')]")
    journal_id = fields.Many2one(
        'account.journal',
        'Journal',
        readonly=False,
        track_visibility='onchange'
    )
    payment_method_id = fields.Many2one("payment.method", string="Payment Method", domain="[('type', '=', 'creditcard'),('is_active','=',True)]",required=True)
    payment_id = fields.Many2one("account.payment", string="Receipt/Payment", compute='_compute_payment_id')
    voucher_id = fields.Many2one("account.voucher", string="Sale/Purchase", compute='_compute_voucher_id')
    format_type = fields.Selection(
        string="Format Credit Card",
        selection=[
            ('visa', 'Visa'),
            ('master', 'Master')
        ],
    )
    is_online = fields.Boolean(
        string="Payment gate way online",
        default=False,
    )
    _sql_constraints = [
        # ('name_unique', 'unique (name)', 'Credit Card No. must be unique !')
    ]
    def _compute_voucher_id(self):
        for credit_card in self:
            voucher_id = credit_card.voucher_id.search([('credit_card_id', '=', credit_card.id)], limit=1)
            voucher_line_ids = self.env['account.voucher.payment'].search([('credit_card_id', '=', credit_card.id)])
            for voucher_line in voucher_line_ids:
                voucher_id = voucher_line.voucher_id
            credit_card.voucher_id = voucher_id

    def _compute_payment_id(self):
        for credit_card in self:
            payment_id = credit_card.payment_id.search([('credit_card_id','=', credit_card.id)], limit=1)
            payment_line_ids = self.env['account.paid.line'].search([('credit_card_id','=', credit_card.id)])
            for payment_line in payment_line_ids:
                payment_id = payment_line.payment_id
            credit_card.payment_id = payment_id

    @api.onchange('bank_partner_id')
    def _onchange_bank_partner_id(self):
        self.account_bank_id = self.bank_partner_id.account_bank_id.id

    def create_account_move(self):
        vals = []
        account_move = self.env["account.move"]
        if not self.account_bank_id:
            raise UserError(_("Please select Account Bank"))
        if not self.date_done:
            raise UserError(_("Please select Date Done"))
        credit_card_total = self.credit_card_type == 'outbound' and - self.credit_card_total or self.credit_card_total
        vals.append(
            [
                0,
                0,
                {
                    "account_id": self.account_bank_id.id,
                    "debit": credit_card_total > 0 and abs(credit_card_total) or 0,
                    "credit": credit_card_total < 0 and abs(credit_card_total) or 0,
                    "name": self.name,
                    "date": self.date_done,
                },
            ]
        )

        vals.append(
            [
                0,
                0,
                {
                    "account_id": self.payment_method_id.account_id.id,
                    "debit": credit_card_total < 0 and abs(credit_card_total) or 0,
                    "credit": credit_card_total > 0 and abs(credit_card_total) or 0,
                    "name": self.name,
                    "date": self.date_done,
                },
            ]
        )

        move_id = account_move.create(
            {
                "date": self.date_done,
                "journal_id": self.journal_id.id,
                "ref": self.name,
                "line_ids": vals,
            }

        )
        move_id.post()
        self.move_id = move_id
        return True
    
    def action_confirm(self):
        self.create_account_move()
        self.state = "done"

    def action_assigned(self):
        self.state = "assigned"

    def action_reject(self):
        self.state = 'reject'

    def action_cancel(self):
        self.move_id.button_cancel()
        self.state = "cancel"

    def action_redraft(self):
        self.state = "draft"

    # @api.onchange('partner_id')
    # def onchange_method(self):
    #     self.payee_id = self.partner_id

    def action_credit_card_done(self):
        return {
            'name': _('Done Credit Card'),
            'res_model': 'date.credit.card.done',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.credit_card',
                'active_ids': self.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }
        

# class ResPartnerBank(models.Model):
#     _inherit = "res.partner.bank"
#
#     account_bank_id = fields.Many2one("account.account", string="Account Bank")