# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_update_any_rental_status = fields.Boolean(
        string='อนุญาตปรับสถานะการเช่าได้ทุกสถานะ',
        default=False,
        help='หากติ๊กถูก ผู้ใช้สามารถอัพเดทสถานะ rental_status ได้ทุกสถานะ โดยไม่ต้องเข้าเงื่อนไข'
    )

    # เพิ่ม field ให้ผู้ใช้สามารถอ่านค่าตัวเองได้
    SELF_READABLE_FIELDS = ['allow_update_any_rental_status']

    @api.model
    def _get_self_readable_fields(self):
        """เพิ่ม field ที่ผู้ใช้สามารถอ่านค่าตัวเองได้"""
        return super()._get_self_readable_fields() + ['allow_update_any_rental_status']
