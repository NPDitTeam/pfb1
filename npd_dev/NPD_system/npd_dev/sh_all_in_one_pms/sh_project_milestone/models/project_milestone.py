# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_milestone_manager = fields.Boolean("Milestone Manager ?")


class ProjectMileStone(models.Model):
    _name = 'project.milestone'
    _description = 'Project Milestone'

    name = fields.Char("Title", required=True)
    project_id = fields.Many2one("project.project")
    start_date = fields.Date("Start Date")
    end_date = fields.Date("End Date")
    duration = fields.Float("Duration (Days)", readonly=True,
                            compute='_compute_duration_on_start_end_date')
    rem_day = fields.Float("Remaining (Days)", readonly=True,
                           compute='_compute_remaining_days_on_start_end_date')
    completed_per = fields.Float("Completed (%)", readonly=True)
    state = fields.Selection([('new', 'New'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')],
                             string="State", default='new', readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)
    task_count = fields.Integer("Task count", compute='_compute_task_count')

    def _compute_task_count(self):
        if self:
            for data in self:
                data.task_count = data.env['project.task'].search_count(
                    [('milestone_id', '=', data.id)])

    def button_inprogress(self):
        if self:
            for data in self:
                data.write({'state': 'in_progress'})

    def button_completed(self):
        if self:
            for data in self:
                data.write({'state': 'completed'})

    def button_cancelled(self):
        if self:
            for data in self:
                data.write({'state': 'cancelled'})

    @api.depends('end_date', 'start_date')
    def _compute_remaining_days_on_start_end_date(self):
        if self:
            for data in self:
                if (data.start_date and data.end_date or False):
                    if (data.start_date <= data.end_date or False):
                        curr_dt = datetime.strptime(
                            str(datetime.now().date()), '%Y-%m-%d')
                        end_dt = datetime.strptime(
                            str(data.end_date), '%Y-%m-%d')
                        data.rem_day = (end_dt - curr_dt).days
                else:
                    data.rem_day = 0.0

    @api.depends('end_date', 'start_date')
    def _compute_duration_on_start_end_date(self):
        if self:
            for data in self:
                if (data.start_date and data.end_date or False):
                    if (data.start_date > data.end_date or False):
                        raise UserError(_(
                            'End Date can not be smaller than Start Date'))

                    start_dt = datetime.strptime(
                        str(data.start_date), '%Y-%m-%d')
                    end_dt = datetime.strptime(str(data.end_date), '%Y-%m-%d')
                    data.duration = abs((end_dt - start_dt).days) + 1

                else:
                    data.duration = 0.0


class ProjectTask(models.Model):
    _inherit = 'project.task'

    milestone_id = fields.Many2one("project.milestone", "Milestone")


class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_milestone = fields.Boolean("Is Milestone ?")

    milestone_id = fields.Many2one("project.milestone", "Milestone")
    milestone_count = fields.Integer(
        "Milestone count", compute='_compute_milestone_count')

    def _compute_milestone_count(self):
        if self:
            for data in self:
                data.milestone_count = data.env['project.milestone'].search_count(
                    [('project_id', '=', data.id)])
