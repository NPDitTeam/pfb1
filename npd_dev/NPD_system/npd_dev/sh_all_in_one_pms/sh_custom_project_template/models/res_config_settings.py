# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models

# Default Projest Stages Configuration


class ResCompany(models.Model):
    _inherit = 'res.company'

    sh_project_stage = fields.Many2one(
        comodel_name='project.task.type', string='Default Project Stage')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sh_project_stage = fields.Many2one(
        'project.task.type',  string='Default Project Stage',
        related='company_id.sh_project_stage', readonly=False)
