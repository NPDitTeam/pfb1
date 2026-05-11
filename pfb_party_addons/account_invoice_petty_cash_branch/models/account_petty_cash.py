# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from odoo import fields, models, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError


class AccountPettyCash(models.Model):
    _inherit = 'petty.cash'
    branch_id = fields.Many2one('res.branch', string='Branch')
    @api.model
    def default_get(self, default_fields):
        res = super(AccountPettyCash, self).default_get(default_fields)
        branch_id = False

        if self._context.get('branch_id'):
            branch_id = self._context.get('branch_id')
        elif self.env.user.branch_id:
            branch_id = self.env.user.branch_id.id
        res.update({
            'branch_id' : branch_id
        })
        return res         

class AccountPettyCashExpense(models.Model):
    _inherit = 'petty.cash.expense'
    branch_id = fields.Many2one('res.branch', string='Branch')
    @api.model
    def default_get(self, default_fields):
        res = super(AccountPettyCashExpense, self).default_get(default_fields)
        branch_id = False

        if self._context.get('branch_id'):
            branch_id = self._context.get('branch_id')
        elif self.env.user.branch_id:
            branch_id = self.env.user.branch_id.id
        res.update({
            'branch_id' : branch_id
        })
        return res         

