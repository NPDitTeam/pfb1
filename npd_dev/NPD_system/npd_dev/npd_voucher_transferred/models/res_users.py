# -*- coding: utf-8 -*-
from odoo import fields, models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    show_transfer_button = fields.Boolean(
        string='แสดงปุ่มโอนแล้ว (Voucher)',
        default=False,
        help='ติ๊กเพื่อให้ผู้ใช้นี้สามารถเห็นและกดปุ่ม "โอนแล้ว" บนใบแจ้งหนี้ได้',
    )

    @api.model
    def _get_transfer_group(self):
        return self.env.ref('npd_voucher_transferred.group_voucher_transfer', raise_if_not_found=False)

    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        if 'show_transfer_button' in vals:
            group = self._get_transfer_group()
            if group:
                for user in self:
                    if user.show_transfer_button:
                        # เพิ่ม user เข้า group
                        group.sudo().write({'users': [(4, user.id)]})
                    else:
                        # ลบ user ออกจาก group
                        group.sudo().write({'users': [(3, user.id)]})
        return res

    @api.model
    def create(self, vals):
        user = super(ResUsers, self).create(vals)
        if vals.get('show_transfer_button'):
            group = self._get_transfer_group()
            if group:
                group.sudo().write({'users': [(4, user.id)]})
        return user
