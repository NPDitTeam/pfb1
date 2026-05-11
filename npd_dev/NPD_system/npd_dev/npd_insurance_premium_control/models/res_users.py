# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_edit_insurance_premium = fields.Boolean(
        string='อนุญาตให้แก้ไขค่าประกันที่ต้องการ',
        default=False,
        help='ถ้าติ๊กถูก ผู้ใช้นี้สามารถแก้ไขฟิลด์ "กรอกจำนวนค่าประกันที่ต้องการ" ในใบสั่งขายได้ '
             'ถ้าไม่ติ๊ก จะไม่สามารถแก้ไขได้'
    )
