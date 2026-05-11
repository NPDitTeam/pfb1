from odoo import models, fields

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    stock_initial = fields.Float(string="ปริมาณตั้งต้น")
