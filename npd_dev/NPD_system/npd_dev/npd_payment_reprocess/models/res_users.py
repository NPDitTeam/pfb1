# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_payment_reprocess = fields.Boolean(
        string='ดำเนินการรับชำระใหม่',
        default=False,
    )

    def write(self, vals):
        res = super().write(vals)
        if 'allow_payment_reprocess' in vals:
            self._sync_reprocess_group()
        return res

    @api.model
    def create(self, vals):
        res = super().create(vals)
        if res.allow_payment_reprocess:
            res._sync_reprocess_group()
        return res

    def _sync_reprocess_group(self):
        """Sync Boolean field กับ hidden group เพื่อควบคุมเมนู"""
        group = self.env.ref(
            'npd_payment_reprocess.group_payment_reprocess',
            raise_if_not_found=False,
        )
        if not group:
            return
        for user in self:
            if user.allow_payment_reprocess:
                group.sudo().write({'users': [(4, user.id)]})
            else:
                group.sudo().write({'users': [(3, user.id)]})
