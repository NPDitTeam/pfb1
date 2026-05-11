from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError


class StockMoveLineInherit(models.Model):
    _inherit = "stock.move.line"

    picking_type_id = fields.Many2one(
                'stock.picking.type',
                compute="_depends_picking_type",
                string="Operation type"
            )

    @api.depends('move_id')
    def _depends_picking_type(self):
        for rec in self:
            rec.picking_type_id = rec.move_id.picking_id.picking_type_id.id
