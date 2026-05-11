# -*- coding: utf-8 -*-

from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    employee_code = fields.Char(string='รหัสพนักงาน')
