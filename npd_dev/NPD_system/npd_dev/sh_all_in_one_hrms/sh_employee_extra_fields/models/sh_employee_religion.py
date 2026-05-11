# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# Employee Religion


class ShEmployeeReligion(models.Model):
    _name = 'sh.employee.religion'
    _description = 'Sh Employee Religion'

    name = fields.Char('Name', required=True)
