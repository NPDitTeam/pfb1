# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields, api
from datetime import date, datetime
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    start_date = fields.Datetime("Start Date")
    end_date = fields.Datetime("End Date")

    def _get_duration(self, start_date, end_date):
        """ Get the duration value between the 2 given dates. """
        if end_date and start_date:
            diff = fields.Datetime.from_string(
                end_date) - fields.Datetime.from_string(start_date)
            if diff:
                unit_amount = float(diff.days) * 24 + \
                    (float(diff.seconds) / 3600)

                return round(unit_amount, 2)
            return 0.0

    @api.onchange('start_date', 'end_date')
    def onchange_duration_custom(self):
        if self and self.start_date and self.end_date:
            start_date = self.start_date
            date = start_date.date()
            self.date = date
            self.unit_amount = self._get_duration(
                self.start_date, self.end_date)


class TaskTimeAccountLine(models.Model):
    _name = 'task.time.account.line'
    _description = 'Task Time Account Line'

    def _get_default_start_time(self):
        if self.env.user.task_id:
            return self.env.user.start_time

    def _get_default_end_time(self):
        return datetime.now()

    def _get_default_duration(self):
        active_model = self.env.context.get('active_model')
        if active_model == 'project.task':
            active_id = self.env.context.get('active_id')
            if self.env.user and self.env.user.task_id:
                task_search = self.env['project.task'].search(
                    [('id', '=', active_id)], limit=1)
                diff = fields.Datetime.from_string(
                    fields.Datetime.now()) - fields.Datetime.from_string(
                        self.env.user.start_time)
                if diff:
                    duration = float(diff.days) * 24 + (float(diff.seconds) /
                                                        3600)
                    return round(duration, 2)

    name = fields.Text("Description", required=True)
    start_date = fields.Datetime("Start Date",
                                 default=_get_default_start_time,
                                 readonly=True)
    end_date = fields.Datetime("End Date",
                               default=_get_default_end_time,
                               readonly=True)
    duration = fields.Float("Duration (HH:MM)",
                            default=_get_default_duration,
                            readonly=True)

    def end_task(self):

        context = dict(self.env.context or {})
        active_model = context.get('active_model', False)
        active_id = context.get('active_id', False)

        vals = {
            'name': self.name,
            'unit_amount': self.duration,
            'amount': self.duration,
            'date': datetime.now()
        }

        if active_model == 'project.task':
            if active_id and self.env.user and self.env.user.task_id:
                task_search = self.env['project.task'].search(
                    [('id', '=', active_id)], limit=1)

                if task_search:
                    vals.update({'start_date': self.env.user.start_time})
                    vals.update({'end_date': datetime.now()})
                    vals.update({'task_id': task_search.id})

                    if task_search.project_id:
                        vals.update({'project_id': task_search.project_id.id})
                        act_id = self.env['project.project'].sudo().browse(
                            task_search.project_id.id).analytic_account_id

                        if act_id:
                            vals.update({'account_id': act_id.id})

                    task_search.sudo().write({
                        'start_time':
                        None,
                        'task_running':
                        False,
                        'task_runner_ids': [(3, self.env.user.id)]
                    })

        timesheet_line = self.env['account.analytic.line'].sudo().search(
            [('task_id', '=', task_search.id),
             ('employee_id.user_id', '=', self.env.uid),
             ('end_date', '=', False)],
            limit=1)
        if timesheet_line:
            timesheet_line.write(vals)
        self.sudo()._cr.commit()
        self.env.user.write({'task_id': False, 'start_time': None})
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    task_running = fields.Boolean("Task Running")
    task_runner = fields.Char(string="Task Runner")
    start_time = fields.Datetime("Start Time", copy=False)
    end_time = fields.Datetime("End Time", copy=False)
    total_time = fields.Char("Total Time", copy=False)
    duration = fields.Float('Real Duration', compute='_compute_duration')
    is_user_working = fields.Boolean("Is User working ?",
                                     compute='_compute_is_user_working')
    end_task_bool = fields.Boolean("End Task",
                                   default=False,
                                   compute='_compute_end_task_bool')
    start_task_bool = fields.Boolean("Start Task",
                                     compute='_compute_start_task_bool')

    start_id = fields.Integer()
    task_runner_ids = fields.Many2many('res.users',
                                       'runner_user_rel',
                                       'user_id',
                                       'runner_id',
                                       string="Runner")
    responsible_user_names = fields.Char(compute='onchange_task_runner_ids')

    check_bool_enable_task_timer = fields.Boolean(
        related="company_id.enable_task_timer")

    @api.depends('task_runner_ids')
    def onchange_task_runner_ids(self):
        for rec in self:

            rec.responsible_user_names = False
            names = ''
            count = 0
            for user in rec.task_runner_ids:
                if count == 0:
                    names = user.name
                    count = 1
                else:
                    names += ',' + user.name

            rec.responsible_user_names = names

    def _compute_start_task_bool(self):
        for rec in self:
            rec.start_task_bool = True
            timesheet_line = self.env['account.analytic.line'].sudo().search(
                [('task_id', '=', rec.id),
                 ('employee_id.user_id', '=', self.env.uid),
                 ('end_date', '=', False), ('unit_amount', '=', 0.0)],
                limit=1)
            if timesheet_line:
                rec.start_task_bool = False

    def _compute_end_task_bool(self):
        for rec in self:
            rec.end_task_bool = False
            timesheet_line = self.env['account.analytic.line'].sudo().search(
                [('task_id', '=', rec.id),
                 ('employee_id.user_id', '=', self.env.uid),
                 ('end_date', '=', False), ('unit_amount', '=', 0.0)],
                limit=1)
            if timesheet_line:
                rec.end_task_bool = True

    @api.model
    def get_duration(self, task):
        if self.env.user and self.env.user.task_id:
            if self.env.user.start_time:
                diff = fields.Datetime.from_string(
                    fields.Datetime.now()) - fields.Datetime.from_string(
                        self.env.user.start_time)
                if diff:
                    duration = float(diff.days) * 24 + (float(diff.seconds) /
                                                        3600)
                    return diff.total_seconds() * 1000

    def _compute_is_user_working(self):
        for rec in self:
            rec.is_user_working = False
            if rec and rec.timesheet_ids:
                timesheet_line = rec.timesheet_ids.filtered(
                    lambda x: x.task_id.id == rec.id and x.end_date == False
                    and x.start_date != False)
                if timesheet_line:
                    rec.is_user_working = True
                else:
                    rec.is_user_working = False

    @api.depends('timesheet_ids.unit_amount')
    def _compute_duration(self):
        for rec in self:
            rec.duration = 0.0
            if rec and rec.timesheet_ids:
                timesheet_line = rec.timesheet_ids.filtered(
                    lambda x: x.task_id.id == rec.id and x.end_date == False
                    and x.start_date != False)
                if timesheet_line:
                    rec.duration = timesheet_line[0].unit_amount

    def action_task_start(self):
        #         if self.task_running == True:
        #             raise UserError(" This task has been already started by another user !")
        #
        if self.env.user.task_id:
            raise UserError("You can not start 2 tasks at same time !")

        self.sudo().start_time = datetime.now()
        # add entry in line

        vals = {'name': '/', 'date': datetime.now()}

        if self:
            vals.update({'start_date': datetime.now()})
            vals.update({'task_id': self.id})

            if self.project_id:
                vals.update({'project_id': self.project_id.id})
                act_id = self.env['project.project'].sudo().browse(
                    self.project_id.id).analytic_account_id

                if act_id:
                    vals.update({'account_id': act_id.id})

        usr_id = self.env.user.id
        if usr_id:
            emp_search = self.env['hr.employee'].search(
                [('user_id', '=', usr_id)], limit=1)

            if emp_search:
                vals.update({'employee_id': emp_search.id})

        self.env['account.analytic.line'].sudo().create(vals)
        self.env.user.write({'task_id': self.id, 'start_time': datetime.now()})
        self.write({
            'task_running': True,
            'task_runner': self.env.user.name,
            'task_runner_ids': [(4, self.env.user.id)]
        })
        self.sudo()._cr.commit()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def action_user_task_end(self):
        usr_id = self.env.user
        if usr_id and usr_id.task_id:
            usr_id.task_id.action_task_end()
        return {}

    def action_task_end(self):
        self.sudo().end_time = datetime.now()
        self.sudo().start_time = self.env.user.start_time
        if self.id != self.env.user.task_id.id:
            raise UserError("You cannot End this task !")

        tot_sec = (self.end_time - self.env.user.start_time).total_seconds()
        tot_hours = round((tot_sec / 3600.0), 2)

        self.sudo().total_time = tot_hours
        #         self.write({'task_running':False})
        return {
            'name': "End Task",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'task.time.account.line',
            'target': 'new',
        }
