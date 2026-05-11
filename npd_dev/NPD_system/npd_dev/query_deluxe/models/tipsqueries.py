from odoo import models, fields

class TipsQueries(models.Model):
    _name = 'tipsqueries'
    _description = 'Tips Queries'

    name = fields.Char(string='Name')
    description = fields.Text(string='Description')
