# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh Ot Types object


class ShPromotionTypes(models.Model):
    _name = 'sh.promotion.types'
    _description = "Promotion Types"

    name = fields.Char(string='Promotion Types', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
