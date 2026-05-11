# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# Resignation Type object


class ShResignationType(models.Model):
    _name = 'sh.resignation.types'
    _description = 'Resignation Type'

    name = fields.Char(string='Resignation Type', required=True)
