# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_project_stage = fields.Boolean(
        "Enable Project Stages",
        implied_group='sh_all_in_one_pms.group_enable_project_stage')