from odoo import fields, models, api


class AccountCheque(models.Model):
    _inherit = 'account.cheque'

    cheque_number_id = fields.Many2one(
        comodel_name='cheque.number',
        string='Cheque Number',
        domain=[('cheque_id','=',False)]
    )

    @api.onchange('cheque_number_id')
    def onchange_cheque_number_id(self):
        self.name = self.cheque_number_id.name
        print('self.name',self.name)