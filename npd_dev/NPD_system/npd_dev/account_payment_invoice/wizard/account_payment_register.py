# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'
    _description = 'Register Payment'

    payment_method_one_id = fields.Many2one("payment.method",
                                            string="Payment Method",
                                            required=True,
                                            domain="[('type', 'in', ['cash','bank','cheque']),('is_active','=',True)]")
    # cheque_id = fields.Many2one("account.cheque", string="Cheque",
    #                             domain="[('state', '=', 'draft')]")

    def _create_payment_vals_from_wizard(self):
        payment_vals = super()._create_payment_vals_from_wizard()
        payment_vals['payment_method_one_id'] = self.payment_method_one_id.id
        active_id = self._context.get('active_ids')
        invoice = self.env['account.move'].browse(active_id)
        vals = {
            'invoice_id': invoice.id,
            "paid_total": self.amount + invoice.wht_amt,
            "amount_due": invoice.amount_residual,
            "paid": True,
            "wht_total": invoice.wht_amt or 0,
            "wht_base": invoice.wht_base or 0,
        }

        payment_vals['invoice_ids'] = [(0, 0, vals)]
        return payment_vals
