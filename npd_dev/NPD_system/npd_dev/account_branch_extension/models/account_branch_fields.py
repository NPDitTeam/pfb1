from odoo import models, fields

class AccountAdvance(models.Model):
    _inherit = 'account.advance'

    branch_id = fields.Many2one( string='Branch', required=True)

class AccountAdvanceClear(models.Model):
    _inherit = 'account.advance.clear'

    branch_id = fields.Many2one(string='Branch', required=True)

class AccountAdvanceRequest(models.Model):
    _inherit = 'account.advance.request'

    branch_id = fields.Many2one(string='Branch', required=True)
