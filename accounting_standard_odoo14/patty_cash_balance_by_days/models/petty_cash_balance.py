from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class PettyCashBalance(models.Model):
    _name = 'petty.cash.balance'
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _description = _('petty.cash.balance')
    

    name = fields.Char(string=_('Name'),readonly=True)
    date = fields.Date(
        string=_('Date'),
        default=fields.Date.context_today,
        required=True,
        tracking=5,
    )
    petty_cash_id = fields.Many2one(
        string=_('Petty Cash'),
        comodel_name='petty.cash',
        tracking=5,
    )
    balance = fields.Float(
        string=_('Petty Cash Balance'),
        related='petty_cash_id.balance',
        store=True, 
        digits='Account'
    )
    petty_balance_line_ids = fields.One2many(
        string=_('petty_balance_line_ids'),
        comodel_name='petty.balance.line',
        inverse_name='petty_balance_id',
    )
    total = fields.Float(
        string=_('Total'), 
        digits='Account',
        readonly=True,
        compute='_compute_total',
        tracking=5,
        )
    note = fields.Text(string=_('Note'),tracking=5,)
    state = fields.Selection(
        string=_('state'),
        selection=[
            ('draft', 'Draft'),
            ('done', 'Done'),
              ('cancel', 'Cancel'),
        ],
        default='draft', 
        tracking=5,
    )
    @api.model_create_multi
    def create(self, vals_list):
        cash_bal = super().create(vals_list)
        for rec in cash_bal:
            if rec.balance != rec.total:
                raise ValidationError(
                    _("Total is not balance please check line and petty cash balance")
                )
        return cash_bal
    
    def write(self, vals):
        cash_bal = super().write(vals)
        for rec in self:
            if rec.balance != rec.total:
                raise ValidationError(
                    _("Total is not balance please check line and petty cash balance")
                )
        return cash_bal
    
    @api.depends('petty_balance_line_ids.total')
    def _compute_total(self):
        for record in self:
            record.total = sum(line.total for line in record.petty_balance_line_ids)

    def action_confirm(self):
        if self.name != "":
            self.name = self.env["ir.sequence"].next_by_code("petty.balance")
        self.state = 'done'

    def action_cancel(self):
        self.state = 'cancel'
    
    def action_reset(self):
        self.state = 'draft'

    
class PettyBalanceLine(models.Model):
    _name = 'petty.balance.line'
    _description = _('petty.balance.line')
    

    petty_balance_id = fields.Many2one(
        string=_('Petty Balance'),
        comodel_name='petty.cash.balance',
    )
    cash_type_id = fields.Many2one(
        string=_('Cash Type'),
        comodel_name='cash.type',
    )
    qty = fields.Integer(string=_('Qty'))
    value = fields.Float(string=_('Value'),related='cash_type_id.value',store=True, digits='Account')
    total = fields.Float(string=_('Total'), digits='Account',readonly=True,compute='_compute_total_line')
    
    @api.depends('qty','cash_type_id')
    def _compute_total_line(self):
        for record in self:
            record.total = record.value * record.qty