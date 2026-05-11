from odoo import api, fields, models


class AccountBilling(models.Model):
    _inherit = "account.billing"

    partner_id = fields.Many2one('res.partner', compute='onchange_bill_type', store=True)

    @api.onchange('bill_type')
    def onchange_bill_type(self):
        print(self.bill_type)
        if self.bill_type == 'out_invoice':
            return {'domain': {'partner_id': [('customer', '=', True), ('parent_id', '=', False)]},
                    'string': {'Customer'}
                    }
        else:
            return {'domain': {'partner_id': [('supplier', '=', True), ('parent_id', '=', False)]},
                    'string': {'Vendor'}
                    }
