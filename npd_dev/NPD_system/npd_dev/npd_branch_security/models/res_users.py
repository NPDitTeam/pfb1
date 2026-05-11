# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    # สิทธิ์สาขา - ค่าเริ่มต้น False (ไม่อนุญาต)
    branch_can_create = fields.Boolean(
        string='สร้างสาขา',
        default=False,
        help='อนุญาตให้สร้างข้อมูลสาขาใหม่'
    )
    branch_can_write = fields.Boolean(
        string='แก้ไขสาขา',
        default=False,
        help='อนุญาตให้แก้ไขข้อมูลสาขา'
    )
    branch_can_delete = fields.Boolean(
        string='ลบสาขา',
        default=False,
        help='อนุญาตให้ลบข้อมูลสาขา'
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            'branch_can_create',
            'branch_can_write',
            'branch_can_delete',
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + [
            'branch_can_create',
            'branch_can_write',
            'branch_can_delete',
        ]
