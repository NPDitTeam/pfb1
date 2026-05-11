# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountCreateCheque(models.TransientModel):
    _name = 'create.account.cheque'
    _description = 'Register Payment'

    name = fields.Char(string="Book Number", required=True)
    number = fields.Integer('Starting Number')
    multi_cheque = fields.Integer(
        string='Multi Cheque',
        required=True)

    def action_create_cheque(self):

        for number in range(self.multi_cheque):
            self.env['cheque.number'].create({
                'name': self.number + int(number),
                'number': self.name,
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
