from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    wht_line_ids = fields.One2many('withholding.tax.cert', 'account_move_id', string='Withholding Tax')


class WithholdingTaxCert(models.Model):
    _inherit = "withholding.tax.cert"

    account_move_id = fields.Many2one('account.move', string='Account Move')