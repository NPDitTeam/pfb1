# -*- coding: utf-8 -*-
from odoo import api, models


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'npd.cancel.lock.mixin']

    _cancel_lock_date_field = 'date'
    _cancel_lock_date_label = 'วันที่รับชำระ'

    @api.model
    def _cancel_lock_scope_domain(self):
        return [('payment_type', '=', 'inbound')]

    def _cancel_lock_in_scope(self):
        return self.payment_type == 'inbound'

    @api.depends('payment_type', 'state', 'date')
    def _compute_cancel_lock_state(self):
        return super(AccountPayment, self)._compute_cancel_lock_state()

    # ตรวจก่อนโค้ดของ account_payment_invoice ซึ่ง commit กลางคัน
    # (ถ้าหลุดทางนี้ไปได้ ก็ยังโดนตรวจซ้ำที่ account.move.button_draft / button_cancel)
    def action_draft(self):
        self._check_cancel_lock()
        return super(AccountPayment, self).action_draft()

    def action_cancel(self):
        self._check_cancel_lock()
        return super(AccountPayment, self).action_cancel()
