# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, _
from odoo.exceptions import ValidationError

class EmployeeConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_mass_approve_leave = fields.Boolean(
        "Enable Employee Mass Approve Leave", implied_group='sh_all_in_one_hrms.group_enable_mass_approve_leave')

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def action_first_approval(self):
        for rec in self:
            if self.env.user.has_group('sh_all_in_one_hrms.group_enable_mass_approve_leave'):
                rec.action_approve()
            else:
                raise ValidationError(_(
                    "You are not authorized to perform this !"))

    def action_second_approval(self):
        for rec in self:
            if self.env.user.has_group(
                    'hr_holidays.group_hr_holidays_manager'):
                rec.action_validate()
            else:
                raise ValidationError(_(
                    "You are not authorized to perform this !"))
