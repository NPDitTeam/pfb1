# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh.idea.categories object


class ShIdeaCategories(models.Model):
    _name = 'sh.idea.categories'
    _description = 'Sh Idea Categories'

    name = fields.Char(string='Idea Categories', required=True)
    department = fields.Many2many('hr.department', string="Department")
    responsible_persons = fields.Many2many(
        'res.users', string="Responsible Persons")
