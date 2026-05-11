from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    partner_id = fields.Many2one('res.partner', compute='onchange_move_type', store=True)

    @api.onchange('move_type')
    def onchange_move_type(self):
        if self.move_type == 'out_invoice' or self.move_type == 'out_refund':
            return {'domain': {'partner_id': [('customer', '=', True), ('parent_id', '=', False)]},
                    'string': {'Customer'}
                    }
        else:
            return {'domain': {'partner_id': [('supplier', '=', True), ('parent_id', '=', False)]},
                    'string': {'Vendor'}
                    }

