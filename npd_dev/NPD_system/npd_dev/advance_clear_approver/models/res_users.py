# -*- coding: utf-8 -*-

from odoo import fields, models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_advance_clear_approver = fields.Boolean(
        string="เป็นผู้ตรวจสอบ Advance Clear",
        default=False,
        help="ติ๊กเลือกถ้าต้องการให้ผู้ใช้นี้เป็นผู้ตรวจสอบ Advance Clear"
    )

    @api.model
    def get_advance_clear_approvers(self):
        """Get all users who are marked as approvers"""
        return self.search([('is_advance_clear_approver', '=', True)])
