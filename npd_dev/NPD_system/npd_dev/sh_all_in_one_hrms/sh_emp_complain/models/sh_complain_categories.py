# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh.complain.categories object


class ShComplainCategories(models.Model):
    _name = 'sh.complain.categories'
    _description = 'Sh Complain Categories'

    name = fields.Char(string='Complain Categories', required=True)
    department = fields.Many2many('hr.department', string="Department")
    responsible_persons = fields.Many2many(
        'res.users', string="Responsible Persons")
