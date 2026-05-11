# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields


class ProjectTemplateTask(models.Model):
    _name = 'project.template.task'
    _description = 'Project Template Task'

    name = fields.Char(string="Task", required=True)
    assigned_to = fields.Many2one("res.users", string="Assigned To")
    description = fields.Html("Description")
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)
    project_template_id = fields.Many2one(
        "project.template", string="Project Template Id")
    sh_task_id = fields.One2many(
        "project.task", "sh_project_template_task_id", string="Task ")

    def action_assign_sub_task(self):
        """ Opens a wizard to assign sub task."""
        # self.ensure_one()

        view = self.env.ref(
            'sh_all_in_one_pms.sh_project_template_task_form_view2')

        return {
            'name': 'Sub Task Template',
            'type': 'ir.actions.act_window',
            'res_model': 'project.template.task',
            'type': 'ir.actions.act_window',
            'views': [(view.id, 'form')],
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
        }
