# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_project_template_task_id = fields.Many2one(
        "project.template.task", string="Project Template")

    @api.model_create_multi
    def create(self, vals_list):
        res = super(ProjectTask, self).create(vals_list)

        parent_id = self.env.context.get("active_id")
        parent_model = self.env.context.get("active_model")

        if parent_model == 'project.template' and parent_id:

            res.sh_project_template_task_id = parent_id

        return res
