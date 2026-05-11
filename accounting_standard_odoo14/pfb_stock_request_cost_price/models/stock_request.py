# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
from odoo import _, api, fields, models


class StockRequest(models.Model):
    _inherit = "stock.request"

    standard_price = fields.Float(
        related="product_id.standard_price",
        store=True,
        string="Cost"
    )