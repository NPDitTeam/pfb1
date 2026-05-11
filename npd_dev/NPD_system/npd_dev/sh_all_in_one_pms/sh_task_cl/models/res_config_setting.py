# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_task_check_list = fields.Boolean()


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_task_check_list = fields.Boolean(
        "Enable Task Check List",
        related='company_id.enable_task_check_list',
        readonly=False)

    group_enable_task_check_list = fields.Boolean(
        "Enable Task Check List ",
        implied_group='sh_all_in_one_pms.group_enable_task_check_list')
