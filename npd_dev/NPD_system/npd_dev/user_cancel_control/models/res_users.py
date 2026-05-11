# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_cancel = fields.Boolean(
        string='อนุญาตให้ยกเลิก',
        default=False,
        help='ถ้าติ๊กถูก ผู้ใช้นี้สามารถยกเลิกการชำระเงิน บันทึก และใบสั่งขายได้ '
             'ถ้าไม่ติ๊ก จะไม่สามารถยกเลิกได้'
    )
