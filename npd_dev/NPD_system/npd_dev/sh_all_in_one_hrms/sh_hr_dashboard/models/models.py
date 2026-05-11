# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class HR(models.Model):
    _inherit = 'hr.employee'

    date_of_joining = fields.Date("Date of Joining")


class HRPublic(models.Model):
    _inherit = 'hr.employee.public'

    date_of_joining = fields.Date("Date of Joining")


class HRDashboard(models.Model):
    _name = 'sh.hr.dashboard'
    _description = 'HR Dashboard'

    name = fields.Char("Name")
