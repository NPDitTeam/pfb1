# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_mass_project_stage = fields.Boolean()


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_mass_project_stage = fields.Boolean(
        "Enable Mass Project Stage",
        related='company_id.enable_mass_project_stage',
        readonly=False)
