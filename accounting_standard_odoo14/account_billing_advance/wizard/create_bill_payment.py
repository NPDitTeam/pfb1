# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class CreateBillPayment(models.TransientModel):
    _name = 'create.bill.payment'

    journal_id = fields.Many2one('account.journal', string='Journal',required=True,domain=[('type','in',('bank','cash'))])
    payment_method_id = fields.Many2one('payment.method', string='Payment Method',required=True, domain="[('is_active','=',True)]")
    date_payment = fields.Date(string='Date Payment',required=True, default=fields.Datetime.now)
   

    def action_create_payments(self):
        active_id = self._context.get('active_ids')
        billing = self.env['account.billing'].browse(active_id)
        invoice_line = []
        bill = billing.billing_line_ids.filtered(lambda d: d.payment_state not in ['paid', 'reversed'])
        if not bill:
            raise UserError(_("Invoice is paid all."))
        for line in bill:
            invoice_line.append((0,0,{
                "invoice_id": line.invoice_id.id, 
                "paid_total": line.billing_total,
                "amount_due": line.total,
                "paid": True,
                "wht_total": line.wht_amt or 0,
                "wht_base": line.wht_base or 0,
                }))

        payment = self.env['account.payment'].create({
            'ref': billing.name,
            'partner_id': billing.partner_id.id,
            'date': self.date_payment,
            'currency_id': billing.currency_id.id,
            'payment_type': billing.bill_type == 'out_invoice' and 'inbound' or 'outbound',
            'journal_id': self.journal_id.id,
            'invoice_ids': invoice_line,
            'payment_method_one_id': self.payment_method_id.id,
            'amount': billing.billing_amount - billing.wht_amount,
        })
        billing.payment_id = payment.id
        return {
            "name": _("Account Payment"),
            "view_mode": "tree,form",
            "res_model": "account.payment",
            "view_id": False,
            "type": "ir.actions.act_window",
            "domain": [("id", "in", payment.ids)],
        }

