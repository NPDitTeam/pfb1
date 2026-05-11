# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    can_edit_force_date = fields.Boolean(
        string='แก้ไขวันที่คืนใน Stock Picking',
        help='อนุญาตให้ผู้ใช้แก้ไขฟิลด์วันที่คืนใน Stock Picking',
        default=False
    )

    def write(self, vals):
        """เมื่ออัพเดท User ให้จัดการกลุ่มตาม checkbox"""
        res = super(ResUsers, self).write(vals)

        if 'can_edit_force_date' in vals:
            try:
                group_edit_force_date = self.env.ref('rental_stock_picking.group_edit_force_date')

                for user in self:
                    if vals['can_edit_force_date']:
                        # เพิ่มเข้ากลุ่ม
                        if group_edit_force_date.id not in user.groups_id.ids:
                            user.groups_id = [(4, group_edit_force_date.id)]
                    else:
                        # ลบออกจากกลุ่ม
                        if group_edit_force_date.id in user.groups_id.ids:
                            user.groups_id = [(3, group_edit_force_date.id)]
            except:
                pass

        return res

    @api.model
    def create(self, vals):
        """เมื่อสร้าง User ใหม่"""
        res = super(ResUsers, self).create(vals)

        if vals.get('can_edit_force_date'):
            try:
                group_edit_force_date = self.env.ref('rental_stock_picking.group_edit_force_date')
                res.groups_id = [(4, group_edit_force_date.id)]
            except:
                pass

        return res