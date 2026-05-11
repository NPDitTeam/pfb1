# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _
from odoo.tools import pycompat


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    license_plate = fields.Char(string='ป้ายทะเบียนรถ')  # ✅ เพิ่มฟิลด์เก็บป้ายทะเบียนรถ
    is_absent = fields.Boolean(string="ขาดงาน", default=False)
    my_activity_date_deadline = fields.Date(string="กิจกรรมถึงกำหนด")