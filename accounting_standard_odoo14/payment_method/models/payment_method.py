from odoo import models, fields,api


class PaymentMethod(models.Model):
    _name = 'payment.method'

    name = fields.Char(
        'Payment Name',
        required=True,
    )
    type = fields.Selection(
        [('cash', 'Cash'),
         ('cheque', 'Cheque'),
         ('bank', 'Bank'),
         ('discount', 'Discount'),
         ('ap', 'AP'),
         ('ar', 'AR'),
         ('other', 'Other')],
        'Payment method',
        required=True
    )
    account_id = fields.Many2one(
        'account.account',
        string="Account",
        required='True',
    )
    is_active = fields.Boolean(string='Active',default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self._default_company_id(),
    )
    @api.model
    def _default_company_id(self):
        return self.env.company
    
    @api.onchange('type')
    def _onchange_type(self):
        self.name = self.type