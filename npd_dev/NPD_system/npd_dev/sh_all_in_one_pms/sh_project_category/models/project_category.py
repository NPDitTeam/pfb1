# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields, api

class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_project_category = fields.Boolean(
        "Enable Project Category", implied_group='sh_all_in_one_pms.group_enable_project_category')


class ProjectCategory(models.Model):
    _name = 'project.category'
    _description = 'Project Description'

    name = fields.Char(string="Project Category", required=True)
    is_active = fields.Boolean("Active", default=True)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    project_category_id = fields.Many2one(
        "project.category", string="Project Category")


class ProjectTask(models.Model):
    _inherit = 'project.task'

    project_category_id = fields.Many2one(
        "project.category", string="Project Category")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            project_id = vals.get('project_id') or self.env.context.get('default_project_id')
            if project_id:
                project = self.env["project.project"].search([('id','=',project_id)])
                if project and project.project_category_id:
                    vals.update({'project_category_id': project.project_category_id.id})

        tasks = super(ProjectTask, self).create(vals_list)
        return tasks

    @api.onchange('project_id')
    def onchange_project_id(self):

        if self:
            if self.project_id and self.project_id.project_category_id:
                self.project_category_id = self.project_id.project_category_id
            else:
                self.project_category_id = ''
