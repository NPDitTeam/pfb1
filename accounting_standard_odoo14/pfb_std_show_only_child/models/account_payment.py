from odoo import api, fields, models


class AccountPaymemt(models.Model):
    _inherit = "account.payment"

    partner_id = fields.Many2one('res.partner', compute='onchange_payment_type', store=True)

    @api.onchange('payment_type')
    def onchange_payment_type(self):
        print(self.payment_type)
        if self.payment_type == 'inbound':
            return {'domain': {'partner_id': [('customer', '=', True), ('parent_id', '=', False)]},
                    'string': {'Customer'}
                    }
        else:
            return {'domain': {'partner_id': [('supplier', '=', True), ('parent_id', '=', False)]},
                    'string': {'Vendor'}
                    }
