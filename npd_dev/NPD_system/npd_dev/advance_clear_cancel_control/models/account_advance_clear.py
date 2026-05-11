# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError


class AccountAdvanceClear(models.Model):
    _inherit = 'account.advance.clear'

    allow_cancel_advance_clear_show = fields.Boolean(
        string="Show Cancel Advance Clear",
        compute="_compute_allow_cancel_advance_clear_show",
        store=False,
    )

    @api.depends()
    def _compute_allow_cancel_advance_clear_show(self):
        for rec in self:
            rec.allow_cancel_advance_clear_show = self.env.user.allow_cancel_advance_clear

    def action_cancel_draft(self):
        if not self.env.user.allow_cancel_advance_clear:
            raise UserError(
                'คุณไม่ได้รับอนุญาตให้ยกเลิก Advance Clear นี้ '
                'กรุณาติดต่อผู้ดูแลระบบ'
            )
        return super(AccountAdvanceClear, self).action_cancel_draft()

    def cancel_advance(self):
        if not self.env.user.allow_cancel_advance_clear:
            raise UserError(
                'คุณไม่ได้รับอนุญาตให้ยกเลิก Advance Clear นี้ '
                'กรุณาติดต่อผู้ดูแลระบบ'
            )
        return super(AccountAdvanceClear, self).cancel_advance()
