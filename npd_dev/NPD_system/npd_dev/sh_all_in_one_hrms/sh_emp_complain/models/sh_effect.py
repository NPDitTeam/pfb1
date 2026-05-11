# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh. Effect  object


class ShEffect(models.Model):
    _name = 'sh.effect.model'
    _description = 'Sh Effect'

    name = fields.Char(string='Name', required=True)
