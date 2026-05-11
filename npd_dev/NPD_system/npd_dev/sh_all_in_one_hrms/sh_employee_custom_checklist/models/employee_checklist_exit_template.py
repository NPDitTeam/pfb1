# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models


class EmployeeExitCustomChecklist(models.Model):
    _name = "employee.exit.custom.checklist.template"
    _description = "Employee Exit Custom Checklist Template"
    _order = 'sequence,name, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=1)
    exit_checklist_template = fields.Many2many(
        'employee.exit.custom.checklist',
        relation='employee_exit_checklist_template_table',
        string='Check List')
