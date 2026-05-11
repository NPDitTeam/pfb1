# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    name = fields.Char(string='Number', copy=False, readonly=False, index=True,
                       tracking=True)

    @api.depends('move_id.name')
    def name_get(self):
        return [(payment.id, payment.name or _('Draft Payment')) for payment in self]

    def action_post(self):
        super(AccountPayment, self).action_post()
        if self.name is False:
            self.name = self.get_seq_payment()

    def get_seq_payment(self):
        if self.payment_type == "inbound":
            return self.env["ir.sequence"].next_by_code("customer.payment", sequence_date=self.date)
        else:
            return self.env["ir.sequence"].next_by_code("supplier.payment", sequence_date=self.date)


    @api.depends('payment_type', 'journal_id')
    def _compute_payment_method_id(self):
        super(AccountPayment, self)._compute_payment_method_id()
        for pay in self:
            if not pay.payment_method_id:
                pay.payment_method_id = 1


