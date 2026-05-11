# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    account_payment_lock_draft_date = fields.Boolean(
        string='สามารถ รีเซ็ตเป็นแบบร่าง และ วันที่',
        default=False
    )

