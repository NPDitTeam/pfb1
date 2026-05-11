# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    bypass_rental_tax_lock = fields.Boolean(
        string='ข้ามการล็อกภาษี',
        default=False,
        help='ถ้าติ๊กถูก ผู้ใช้สามารถเปลี่ยนภาษีได้ทั้งในใบสั่งขายประเภทเช่าและสมุดรายวันที่กำหนด'
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['bypass_rental_tax_lock']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['bypass_rental_tax_lock']
