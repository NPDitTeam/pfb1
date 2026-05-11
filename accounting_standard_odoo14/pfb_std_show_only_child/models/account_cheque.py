from odoo import api, fields, models


class AccountCheque(models.Model):
    _inherit = "account.cheque"

    partner_id = fields.Many2one('res.partner', compute='onchange_cheque_type', store=True)
    payee_id = fields.Many2one('res.partner', compute='onchange_cheque_type_payee', store=True, strin="Payee Cheque")

    @api.onchange('cheque_type')
    def onchange_cheque_type(self):
        print(self.cheque_type)
        if self.cheque_type == 'inbound':
            return {'domain': {'partner_id': [('customer', '=', True), ('parent_id', '=', False)]},
                    'string': {'Customer'}
                    }
        else:
            return {'domain': {'partner_id': [('supplier', '=', True), ('parent_id', '=', False)]},
                    'string': {'Vendor'}
                    }

    @api.onchange('cheque_type')
    def onchange_cheque_type_payee(self):
        if self.cheque_type == 'inbound':
            return {'domain': {'payee_id': [('customer', '=', True), ('parent_id', '=', False)]},
                    }
        else:
            return {'domain': {'payee_id': [('supplier', '=', True), ('parent_id', '=', False)]},
                    }

