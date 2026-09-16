# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    lock_salary_fields = fields.Boolean(
        string='ล็อคการแก้ไขค่าจ้าง/เงินเพิ่ม',
        help='ถ้าติ๊กถูก ผู้ใช้คนนี้จะไม่สามารถแก้ไขฟิลด์ ค่าจ้าง, เงินค่าครองชีพ, '
             'เงินประจำตำแหน่ง, เงินค่าประสบการณ์ และเงินค่าวิชาชีพ ในข้อมูลพนักงานได้',
    )
