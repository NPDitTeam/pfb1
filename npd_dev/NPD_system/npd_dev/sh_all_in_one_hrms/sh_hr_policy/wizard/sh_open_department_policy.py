# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh Ot reject Wizard


class ShDepartmentPolicyWizard(models.TransientModel):
    _name = 'sh.department.policy.wizard'
    _description = "Department Policy Wizard"

    department_id = fields.Many2one('hr.department', string="Department")
    sh_policy = fields.Html(related='department_id.sh_department_policy')
