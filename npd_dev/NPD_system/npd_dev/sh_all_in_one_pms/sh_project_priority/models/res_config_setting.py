# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_project_priority = fields.Boolean()


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_project_priority = fields.Boolean(
        "Enable Project Priority",
        related='company_id.enable_project_priority',
        readonly=False)
