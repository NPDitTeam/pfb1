# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh Ot Types object


class ShOtTypes(models.Model):
    _name = 'sh.ot.types'
    _description = "Overtime Types"

    name = fields.Char(string='Overtime Types', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
