# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields


class ProjectTemplate(models.Model):
    _name = 'project.template'
    _description = 'Project Template'

    name = fields.Char("Template", required=True)
    project_template_task_ids = fields.One2many(
        "project.template.task", "project_template_id", string="Project Template Task")
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)
    templ_active = fields.Boolean("Active", default=True)
