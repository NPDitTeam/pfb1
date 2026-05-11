# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
from odoo import _, api, fields, models

class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _default_user(self):
        return self.env.context.get('user_id', self.env.user.id)

    purchase_user_id = fields.Many2one('res.users', string='Purchase Representative',default=_default_user)




class PurchaseOrder(models.Model):
    _inherit = "purchase.order"


    def _prepare_invoice(self):
        vals =  super(PurchaseOrder, self)._prepare_invoice()
        vals.update({
            'purchase_user_id': self.user_id.id
        })
        return vals