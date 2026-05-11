# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_hr_dashboard = fields.Boolean(
        "Enable My Dashboard", implied_group='sh_all_in_one_hrms.group_enable_hr_dashboard')


class ShMedicalType(models.Model):
    _name = "sh.medical.type"
    _description = "Medical Type"
    _order = "id desc"
    _rec_name = "name"

    name = fields.Char("Name", required=True)
