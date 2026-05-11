# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, api, fields
from datetime import datetime
from dateutil.relativedelta import relativedelta


class HrHolidays(models.Model):
    _inherit = 'hr.leave'

    leave_summary_id = fields.Many2many(
        "sh.leave.summary", string='Leaves Summary')

    @api.model
    def scheduler_leave_notification(self):
        if self.env.user.company_id.sh_enable_automatic_leave == True and self.env.user.has_group('sh_all_in_one_hrms.group_enable_emp_leave_notification'):
            week = datetime.now().date() - relativedelta(weeks=1)
            month = datetime.now().date() - relativedelta(months=1)

            weekly_object = self.env['hr.leave'].search(
                [('request_date_from', '>=', week)])

            monthly_obj = self.env['hr.leave'].search(
                [('request_date_from', '>=', month)])

            if (self.env.user.company_id.sh_automatic_leave == 'weekly' or self.env.user.company_id.sh_automatic_leave == 'both') and weekly_object:

                for employee_id in self.env['hr.employee'].search([]):

                    line_ids = []
                    employees = self.env['hr.leave'].search(
                        [('request_date_from', '>=', week), ('employee_id', '=', employee_id.id)])
                    if employees:
                        for emp in employees:
                            line_ids.append(emp.id)

                        vals = {
                            'leave_ids': [(6, 0, line_ids)],
                            'start_date': week,
                            'end_date': datetime.now().date(),
                            'employee_id': employee_id.id,
                        }

                        summary = self.env["sh.leave.summary"].create(vals)

                        template_id = self.env.ref(
                            'sh_all_in_one_hrms.sh_template_employee_all_leave_email')
                        if template_id:
                            if summary.employee_id and summary.employee_id.work_email and summary.employee_id.parent_id and summary.employee_id.parent_id.work_email:

                                template_id.send_mail(
                                    summary.id, force_send=True)
                                line_ids.clear()

            if (self.env.user.company_id.sh_automatic_leave == 'monthly' or self.env.user.company_id.sh_automatic_leave == 'both') and monthly_obj:

                for employee_id in self.env['hr.employee'].search([]):

                    line_ids = []
                    employees = self.env['hr.leave'].search(
                        [('request_date_from', '>=', month), ('employee_id', '=', employee_id.id)])
                    if employees:
                        for emp in employees:
                            line_ids.append(emp.id)

                        vals = {
                            'leave_ids': [(6, 0, line_ids)],
                            'start_date': month,
                            'end_date': datetime.now().date(),
                            'employee_id': employee_id.id,
                        }

                        summary = self.env["sh.leave.summary"].create(vals)
                        line_ids.clear()
                        template_id = self.env.ref(
                            'sh_all_in_one_hrms.sh_template_employee_all_leave_email')
                        if template_id:
                            if summary.employee_id and summary.employee_id.work_email and summary.employee_id.parent_id and summary.employee_id.parent_id.work_email:

                                template_id.send_mail(
                                    summary.id, force_send=True)

    @api.model
    def create(self, values):   # Done by Employee

        res = super(HrHolidays, self).create(values)
        if res and res.state == 'confirm' and self.env.user.has_group('sh_all_in_one_hrms.group_enable_emp_leave_notification'):  # If in confirm state

            template_id = self.env.ref(
                'sh_all_in_one_hrms.sh_template_employee_request_leave_email'
            )
            if template_id:
                if(
                    res.employee_id and
                    res.employee_id.work_email and
                    res.employee_id.parent_id and
                    res.employee_id.parent_id.work_email
                ):
                    template_id.send_mail(res.id, force_send=True)

        return res

    def write(self, values):  # Done by Employee

        res = super(HrHolidays, self).write(values)
        if(
            res and
            values.get('holiday_status_id', False) or
            values.get('date_from', False) or
            values.get('date_to', False) or
            values.get('number_of_days_temp', False) or
            values.get('name', False)
        ) and self.env.user.has_group('sh_all_in_one_hrms.group_enable_emp_leave_notification'):

            template_id = self.env.ref(
                'sh_all_in_one_hrms.sh_template_employee_request_leave_email'
            )
            if self and template_id:
                for rec in self:
                    if(
                        rec.employee_id and
                        rec.employee_id.work_email and
                        rec.employee_id.parent_id and
                        rec.employee_id.parent_id.work_email
                    ):
                        template_id.send_mail(rec.id, force_send=True)

        return res

    def action_approve(self):  # Done by HR Officer or Manager

        res = super(HrHolidays, self).action_approve()

        template_id = self.env.ref(
            'sh_all_in_one_hrms.sh_template_hr_manager_leave_respond_email'
        )
        if self and template_id and self.env.user.has_group('sh_all_in_one_hrms.group_enable_emp_leave_notification'):
            for rec in self:
                if(
                    rec.employee_id and
                    rec.employee_id.work_email and
                    rec.employee_id.parent_id and
                    rec.employee_id.parent_id.work_email
                ):
                    template_id.send_mail(rec.id, force_send=True)

        return res

    def action_refuse(self):  # Done by HR Officer or Manager

        res = super(HrHolidays, self).action_refuse()

        template_id = self.env.ref(
            'sh_all_in_one_hrms.sh_template_hr_manager_leave_respond_email'
        )
        if self and template_id and self.env.user.has_group('sh_all_in_one_hrms.group_enable_emp_leave_notification'):
            for rec in self:
                if(
                    rec.employee_id and
                    rec.employee_id.work_email and
                    rec.employee_id.parent_id and
                    rec.employee_id.parent_id.work_email
                ):
                    template_id.send_mail(rec.id, force_send=True)

        return res
