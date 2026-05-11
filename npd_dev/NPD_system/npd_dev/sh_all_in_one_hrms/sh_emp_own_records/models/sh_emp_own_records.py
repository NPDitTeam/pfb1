# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_own_records = fields.Boolean(
        "Enable Employee Own Records", implied_group='sh_all_in_one_hrms.group_enable_own_records')
