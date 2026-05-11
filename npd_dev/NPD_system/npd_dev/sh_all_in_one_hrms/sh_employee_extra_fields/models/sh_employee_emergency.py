# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

class EmployeeRelation(models.Model):
    _name = 'sh.employee.relation'
    _description = 'Employee Relation'

    name = fields.Char('Relation',required=True)

class EmployeeEmergerncy(models.Model):
    _name = 'hr.emp.emmergancy'
    _description = 'Sh Employee Emergency'

    name = fields.Char("Contact Name",required=True)
    employee_id = fields.Many2one('hr.employee',string='Employee')
    relation_id = fields.Many2one('sh.employee.relation', string='Employee Relation')
    contact_number=fields.Char(string='Contact Number')
