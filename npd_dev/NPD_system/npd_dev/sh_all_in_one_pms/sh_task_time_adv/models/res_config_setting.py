# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_task_timer = fields.Boolean()


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_task_timer = fields.Boolean("Enable Task Timer",
                                       related='company_id.enable_task_timer',
                                       readonly=False)
