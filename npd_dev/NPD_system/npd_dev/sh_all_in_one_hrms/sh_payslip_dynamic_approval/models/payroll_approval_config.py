# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PayrollApprovalConfig(models.Model):
    _name = 'sh.payroll.approval.config'
    _description = 'Payroll Approval Configuration'

    name = fields.Char()
    min_amount = fields.Float(string="Minimum Amount", required=True)
    company_ids = fields.Many2many(
        'res.company', string="Allowed Companies", default=lambda self: self.env.user.company_id)
    is_boolean = fields.Boolean(string="User and Employee Always in CC")
    payroll_approval_line = fields.One2many(
        'sh.payroll.approval.line', 'payroll_approval_config_id')

    @api.constrains('payroll_approval_line')
    def approval_line_level(self):
        if self.payroll_approval_line:
            levels = self.payroll_approval_line.mapped('level')
            if len(levels) != len(set(levels)):
                raise ValidationError(_('Levels must be different!!!'))
