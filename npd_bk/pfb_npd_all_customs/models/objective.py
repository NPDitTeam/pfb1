from odoo import models, fields, api, _


class SaleObjective(models.Model):
    _name = 'sale.objective'

    name = fields.Char('Name')