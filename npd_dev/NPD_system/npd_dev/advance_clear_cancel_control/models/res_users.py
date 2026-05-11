# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_cancel_advance_clear = fields.Boolean(
        string='อนุญาตให้ยกเลิก Advance Clear',
        default=False,
        help='ถ้าติ๊กถูก ผู้ใช้นี้สามารถยกเลิก Advance Clear ได้ '
             'ถ้าไม่ติ๊ก จะไม่สามารถยกเลิกได้'
    )
