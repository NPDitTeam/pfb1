# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    can_edit_voucher_lines = fields.Boolean(
        string='อนุญาตให้แก้ไข คืนเงินประกันค่าเช่า',
        default=False,
        help='ถ้าติ๊ก ผู้ใช้สามารถแก้ไข คืนเงินประกันค่าเช่า ใน account voucher ได้'
    )