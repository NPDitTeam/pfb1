# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountBilling(models.Model):
    _inherit = "account.billing"
    _description = "Account Billing"

    billing_amount = fields.Float(string='Bill Amount',compute='_compute_amount')
    wht_amount = fields.Float(string='WHT Amount',compute='_compute_amount')
    payment_id = fields.Many2one('account.payment', string='Payment')
    due_date = fields.Date('Due Date')

    @api.onchange("partner_id", "currency_id", "threshold_date", "threshold_date_type")
    def _onchange_invoice_list(self):
        self.billing_line_ids = False
        Billing_line = self.env["account.billing.line"]
        invoices = self.env["account.move"].browse(self._context.get("active_ids", []))
        if not invoices:
            types = ["in_invoice", "in_refund"]
            if self.bill_type == "out_invoice":
                types = ["out_invoice", "out_refund"]
            invoices = self._get_invoices(self.threshold_date_type, types)
        else:
            if invoices[0].move_type in ["out_invoice", "out_refund"]:
                self.bill_type = "out_invoice"
            else:
                self.bill_type = "in_invoice"
        for line in invoices:
            if line.move_type in ["out_refund", "in_refund"]:
                line.amount_residual = line.amount_residual * (-1)
            self.billing_line_ids += Billing_line.new(
                {
                    "invoice_id": line.id,
                    "total": line.amount_residual,
                    'billing_total': line.amount_residual,
                }
            )


    @api.depends('billing_line_ids.billing_total')
    def _compute_amount(self):
        for bill in self:
            bill.billing_amount = sum([line.billing_total for line in bill.billing_line_ids])
            bill.wht_amount = sum([line.wht_amt for line in bill.billing_line_ids])
    
    def action_create_payment(self):
        return {
            'name': _('Create Bill Payment'),
            'res_model': 'create.bill.payment',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.billing',
                'active_ids': self.ids,
                'billing_amount': self.billing_amount,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }


class AccountBillingLine(models.Model):
    _inherit = "account.billing.line"

    billing_total = fields.Float(string='Billing Total')
    wht_amt = fields.Float(string='WHT', related="invoice_id.wht_amt")
    wht_base = fields.Float(string='WHT Base',related="invoice_id.wht_base")