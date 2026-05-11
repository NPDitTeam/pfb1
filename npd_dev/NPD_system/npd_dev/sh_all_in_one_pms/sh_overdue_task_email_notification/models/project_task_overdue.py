# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models, api
import datetime


class ResCompany(models.Model):
    _inherit = 'res.company'

    notification_bool = fields.Boolean("Overdue Notification ?")
    overdue_days = fields.Integer("Overdue Days")
    start_date_bool = fields.Boolean('Start Date Notification ?')
    start_days = fields.Integer('Start Date Days')

class ProjectTask(models.Model):
    _inherit = 'project.task'

    completed = fields.Boolean("Task Completed", readonly=True)
    start_date = fields.Date(
        string='Start Date', index=True, copy=False, tracking=True)

    def action_task_completed(self):
        self.completed = True


class project_task_overdue_notify(models.Model):
    _name = "project.task.overdue.notify"
    _description = 'Project Task Overdue Notify'

    name = fields.Char("Task")
    project_id = fields.Char("Project")
    user_id = fields.Many2one("res.users", "Assigned To")
    date_deadline = fields.Date("Date Deadline")
    start_date = fields.Date("Start Date")

    email_id = fields.Many2one("project.task.overdue.email", "Email Id")


class project_task_overdue_email(models.Model):
    _name = "project.task.overdue.email"
    _description = 'Project Task Overdue Email'

    name = fields.Char("Task")
    user_id = fields.Many2one("res.users", "Email Users")
    company_id = fields.Many2one("res.company",
                                 "Company Id",
                                 default=lambda self: self.env.user.company_id)
    notify_ids = fields.One2many("project.task.overdue.notify", "email_id",
                                 "Notify Id")

    @api.model
    def start_date_task_notification(self):
        company_object = self.env['res.company'].search([])

        if company_object:

            notify = self.env['project.task.overdue.notify'].search([])
            if notify:
                notify.unlink()
            for comp_rec in company_object:
                if comp_rec.start_date_bool:
                    start_days = comp_rec.start_days

                    date_check = (datetime.datetime.now() +
                                  datetime.timedelta(start_days))

                    task_search = self.env['project.task'].search(
                        [('company_id', '=', comp_rec.id),
                         ('completed', '=', False),
                         ('start_date', '<=', date_check.date())],
                        order="user_id")
                    if task_search:
                        user = 0
                        comp = ''

                        for record in task_search:
                            vals_line = {}

                            if record.user_id:
                                if user != 0 and user != record.user_id:

                                    if notify:
                                        user_email_search = self.env[
                                            'project.task.overdue.email'].search(
                                                [])

                                        if user_email_search:
                                            user_email_search.user_id = user
                                            user_email_search.company_id = comp

                                            template = self.env.ref(
                                                'sh_all_in_one_pms.template_project_task_start_date_notify_email'
                                            )

                                            if template:
                                                mail_res = template.send_mail(
                                                    1, force_send=True)

                                            notify = self.env[
                                                'project.task.overdue.notify'].search([])

                                            if notify:
                                                notify.unlink()

                                if record.user_id.email:

                                    vals_line.update({
                                        'user_id': record.user_id.id,
                                        'email_id': 1
                                    })

                                    vals_line.update({
                                        'name': record.name,
                                        'start_date': record.start_date
                                    })

                                    if record.project_id:
                                        vals_line.update({
                                            'project_id': record.project_id.name
                                        })

                                        nofity_obj = self.env[
                                            'project.task.overdue.notify'].create(vals_line)

                                user = record.user_id
                                comp = record.user_id.company_id

                        if True:  # for last user to send record
                            user_email_search = self.env[
                                'project.task.overdue.email'].search([])

                            if user_email_search:
                                user_email_search.user_id = user
                                user_email_search.company_id = comp

                                template = self.env.ref(
                                    'sh_all_in_one_pms.template_project_task_start_date_notify_email'
                                )

                                if template:
                                    mail_res = template.send_mail(
                                        1, force_send=True)

                                    notify = self.env[
                                        'project.task.overdue.notify'].search([])
                                    if notify:
                                        notify.unlink()

    @api.model
    def notify_employee_overdue_fun(self):
        company_object = self.env['res.company'].search([])
        if company_object:

            notify = self.env['project.task.overdue.notify'].search([])
            if notify:
                notify.unlink()
            for comp_rec in company_object:
                if comp_rec.notification_bool:

                    over_due_days = comp_rec.overdue_days
                    date_check = (datetime.datetime.now() -
                                  datetime.timedelta(over_due_days))
                    task_search = self.env['project.task'].search(
                        [('company_id', '=', comp_rec.id),
                         ('completed', '=', False),
                         ('date_deadline', '<=', date_check.date())],
                        order="user_id")
                    if task_search:
                        user = 0
                        comp = ''

                        for record in task_search:
                            vals_line = {}

                            if record.user_id:
                                if user != 0 and user != record.user_id:

                                    if notify:
                                        user_email_search = self.env[
                                            'project.task.overdue.email'].search(
                                                [])

                                        if user_email_search:
                                            user_email_search.user_id = user
                                            user_email_search.company_id = comp

                                            template = self.env.ref(
                                                'sh_all_in_one_pms.template_project_task_overdue_notify_email'
                                            )

                                            if template:
                                                mail_res = template.send_mail(
                                                    1, force_send=True)

                                            notify = self.env[
                                                'project.task.overdue.notify'].search([])

                                            if notify:
                                                notify.unlink()

                                if record.user_id.email:
                                    vals_line.update({
                                        'user_id': record.user_id.id,
                                        'email_id': 1
                                    })

                                    vals_line.update({
                                        'name': record.name,
                                        'date_deadline': record.date_deadline
                                    })

                                    if record.project_id:
                                        vals_line.update({
                                            'project_id': record.project_id.name
                                        })

                                        nofity_obj = self.env[
                                            'project.task.overdue.notify'].create(vals_line)

                                user = record.user_id
                                comp = record.user_id.company_id

                        if notify:  # for last user to send record
                            user_email_search = self.env[
                                'project.task.overdue.email'].search([])

                            if user_email_search:
                                user_email_search.user_id = user
                                user_email_search.company_id = comp

                                template = self.env.ref(
                                    'sh_all_in_one_pms.template_project_task_overdue_notify_email'
                                )

                                if template:
                                    mail_res = template.send_mail(
                                        1, force_send=True)

                                    notify = self.env[
                                        'project.task.overdue.notify'].search([])
                                    if notify:
                                        notify.unlink()
