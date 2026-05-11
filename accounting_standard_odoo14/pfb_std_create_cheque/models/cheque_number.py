from odoo import fields, models, api


class AccountChequeNumber(models.Model):
    _name = 'cheque.number'
    _description = 'Description'
    # _rec_name = 'name'

    name = fields.Char('Name')
    number = fields.Char('Book Number')
    cheque_id = fields.One2many(
        comodel_name='account.cheque',
        inverse_name='cheque_number_id',
        string='Cheque Number',
        required=True)
