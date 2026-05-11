# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields, _, api
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    project_template_id = fields.Many2one(
        "project.template", string="Project Template")

    def btn_project_generate_task(self):
        # For add task
        if self.project_template_id:
            for record in self.project_template_id.project_template_task_ids:
                vals = {'name': record.name,
                        'project_id': self.id,
                        'description': record.description,
                        }
                if record.assigned_to:
                    vals.update({'user_id': record.assigned_to.id})
                if self.env.company.sh_project_stage:
                    vals.update(
                        {'stage_id': self.env.company.sh_project_stage.id})

                Task = self.env['project.task'].sudo().create(vals)

                # For add sub task
                if record.sh_task_id and Task and self.allow_subtasks:

                    for sub_task in record.sh_task_id:

                        vals = {'name': sub_task.name,
                                'project_id': self.id,
                                'description': sub_task.description,
                                'parent_id': Task.id,
                                }
                        if sub_task.user_id:
                            vals.update(
                                {'user_id': sub_task.user_id.id})

                        if self.env.company.sh_project_stage:
                            vals.update(
                                {'stage_id': self.env.company.sh_project_stage.id})

                        self.env['project.task'].sudo().create(vals)
            return {'type': 'ir.actions.client', 'tag': 'reload'}
        else:
            raise UserError(_('Please Select Project Template.'))

    @api.model_create_multi
    def create(self, vals_list):
        res = super(ProjectProject, self).create(vals_list)

        for vals in vals_list:
            if vals.get('project_template_id'):
                project_template = self.env["project.template"].search(
                    [('id', '=', vals.get('project_template_id'))])

                # For add task
                if project_template and project_template.project_template_task_ids:
                    for task in project_template.project_template_task_ids:
                        vals = {'name': task.name,
                                'project_id': res.id,
                                'description': task.description,
                                }
                        if task.assigned_to:
                            vals.update({'user_id': task.assigned_to.id})
                        if self.env.company.sh_project_stage:
                            vals.update(
                                {'stage_id': self.env.company.sh_project_stage.id})
                        Task = self.env['project.task'].sudo().create(vals)

                        # For add sub task
                        if task.sh_task_id and Task and self.user_has_groups('project.group_subtask_project'):

                            for sub_task in task.sh_task_id:

                                vals = {'name': sub_task.name,
                                        'project_id': res.id,
                                        'description': sub_task.description,
                                        'parent_id': Task.id,
                                        }
                                if sub_task.user_id:
                                    vals.update(
                                        {'user_id': sub_task.user_id.id})
                                if self.env.company.sh_project_stage:
                                    vals.update(
                                        {'stage_id': self.env.company.sh_project_stage.id})

                                self.env['project.task'].sudo().create(vals)

        return res
