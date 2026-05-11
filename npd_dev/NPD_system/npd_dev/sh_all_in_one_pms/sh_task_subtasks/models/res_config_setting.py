# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_task_sub_task = fields.Boolean()


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_task_sub_task = fields.Boolean(
        "Enable Task Subtask",
        related='company_id.enable_task_sub_task',
        readonly=False)
