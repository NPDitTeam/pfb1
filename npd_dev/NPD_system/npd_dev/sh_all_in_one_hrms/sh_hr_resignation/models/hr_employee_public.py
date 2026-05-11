# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    contract_ids = fields.One2many(
        'hr.contract', 'employee_id', string='Employee Contracts')
    contract_id = fields.Many2one(
        'hr.contract', string='Current Contract',
        domain="[('company_id', '=', company_id), ('employee_id', '=', id)]", help='Current contract of the employee')
