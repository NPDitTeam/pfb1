# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models


class UpdatemassStage(models.TransientModel):
    _name = "sh.project.stage.mass.update.wizard"
    _description = "Mass Update Wizard"

    project_task_ids = fields.Many2many('project.task.type', string="Stages")
    update_project_bool = fields.Boolean(string="Update Project")
    update_project_ids = fields.Many2many('project.project', string='Project')
    update_method_project = fields.Selection([
        ("add", "Add"),
        ("replace", "Replace"),
    ],
        default="add")

    def update_record(self):
        if self.update_method_project == 'add':
            for i in self.update_project_ids:
                self.project_task_ids.write({'project_ids': [(4, i.id)]})

        if self.update_method_project == 'replace':
            self.project_task_ids.write(
                {'project_ids': [(6, 0, self.update_project_ids.ids)]})
