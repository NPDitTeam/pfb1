# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models


class Updatemasstag(models.TransientModel):

    _name = "sh.employee.manager.update.mass.tag.wizard"
    _description = "Mass Tag Update Wizard"

    all_hr_employee_ids = fields.Many2many('hr.employee')
    update_job_postion_bool = fields.Boolean(string="Update Job Position")
    update_job_postion_id = fields.Many2one('hr.job', string="Jobs")
    update_emp_manager_bool = fields.Boolean(string="Update Manager")
    update_emp_manager = fields.Many2one('hr.employee', string=" Manager")

    def update_mass_employee_details(self):

        if self.update_job_postion_bool == True:
            self.all_hr_employee_ids.write(
                {'job_id': self.update_job_postion_id.id})

        if self.update_emp_manager_bool == True:
            self.all_hr_employee_ids.write(
                {'parent_id': self.update_emp_manager.id})
