# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models, api


class SHProjectTeam(models.Model):
    _name = 'sh.project.team'
    _description = "Project Teams"

    name = fields.Char(required=True,)
    active = fields.Boolean(default=True,)
    code = fields.Char()
    sh_project_manager_id = fields.Many2one(
        comodel_name='res.users', string='Project Manager')
    notes = fields.Text(string="Note")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)

    sh_team_member_ids = fields.Many2many(
        comodel_name='res.users', string='Team Members',)

    _sql_constraints = [
        ('code_uniq', 'unique (code)', "Code already exists!"),
    ]

    @api.onchange('sh_project_manager_id')
    def _onchange_project_manager_id(self):
        if self.sh_project_manager_id:
            self.sh_team_member_ids = [
                (6, 0, self.sh_project_manager_id.ids)]


class SHProject(models.Model):
    _inherit = 'project.project'

    sh_project_team_id = fields.Many2one(
        comodel_name='sh.project.team', string='Project Team')

    sh_project_team_member_ids = fields.Many2many(
        comodel_name='res.users', string='Team Members')

    @api.onchange('sh_project_team_id')
    def _onchange_project_team_id(self):
        if self.sh_project_team_id:
            for record in self.sh_project_team_id:
                self.sh_project_team_member_ids = [
                    (6, 0, record.sh_team_member_ids.ids)]
        else:
            self.sh_project_team_member_ids = False


class SHTask(models.Model):
    _inherit = 'project.task'

    sh_project_team_id = fields.Many2one(
        comodel_name='sh.project.team', string='Project Team',
        related="project_id.sh_project_team_id", store=True)
