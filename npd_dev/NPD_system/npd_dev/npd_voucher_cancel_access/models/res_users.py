# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_cancel_voucher = fields.Boolean(
        string='อนุญาตยกเลิกใบคืนเงินประกันค่าเช่า',
        compute='_compute_allow_cancel_voucher',
        inverse='_inverse_allow_cancel_voucher',
        store=False,
        help='ถ้าติ๊กถูก = แสดงปุ่ม Cancel\nถ้าไม่ติ๊กถูก = ซ่อนปุ่ม Cancel'
    )

    def _compute_allow_cancel_voucher(self):
        group = self.env.ref('npd_voucher_cancel_access.group_cancel_voucher', raise_if_not_found=False)
        for user in self:
            if group:
                user.allow_cancel_voucher = group in user.groups_id
            else:
                user.allow_cancel_voucher = False

    def _inverse_allow_cancel_voucher(self):
        group = self.env.ref('npd_voucher_cancel_access.group_cancel_voucher', raise_if_not_found=False)
        if not group:
            return
        for user in self:
            if user.allow_cancel_voucher:
                user.groups_id = [(4, group.id)]
            else:
                user.groups_id = [(3, group.id)]

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['allow_cancel_voucher']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['allow_cancel_voucher']
