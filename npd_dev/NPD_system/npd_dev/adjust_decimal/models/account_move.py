from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_open_decimal_adjustment(self):
        """Open the decimal adjustment wizard"""
        self.ensure_one()
        return {
            'name': 'แก้ไขทศนิยม',
            'type': 'ir.actions.act_window',
            'res_model': 'decimal.adjustment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_model': 'account.move',
            },
        }
