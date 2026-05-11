# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from odoo import fields, models, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError


class AccountAdvanceRequest(models.Model):
    _inherit = 'account.advance.request'
    branch_id = fields.Many2one('res.branch', string='Branch')
    @api.model
    def default_get(self, default_fields):
        res = super(AccountAdvanceRequest, self).default_get(default_fields)
        branch_id = False

        if self._context.get('branch_id'):
            branch_id = self._context.get('branch_id')
        elif self.env.user.branch_id:
            branch_id = self.env.user.branch_id.id
        res.update({
            'branch_id' : branch_id
        })
        return res                

class AccountAdvance(models.Model):
    _inherit = 'account.advance'
    branch_id = fields.Many2one('res.branch', string='Branch')
    @api.model
    def default_get(self, default_fields):
        res = super(AccountAdvance, self).default_get(default_fields)
        branch_id = False

        if self._context.get('branch_id'):
            branch_id = self._context.get('branch_id')
        elif self.env.user.branch_id:
            branch_id = self.env.user.branch_id.id
        res.update({
            'branch_id' : branch_id
        })
        return res                

class AccountAdvanceClear(models.Model):
    _inherit = 'account.advance.clear'
    branch_id = fields.Many2one('res.branch', string='Branch')
    @api.model
    def default_get(self, default_fields):
        res = super(AccountAdvanceClear, self).default_get(default_fields)
        branch_id = False

        if self._context.get('branch_id'):
            branch_id = self._context.get('branch_id')
        elif self.env.user.branch_id:
            branch_id = self.env.user.branch_id.id
        res.update({
            'branch_id' : branch_id
        })
        return res                
