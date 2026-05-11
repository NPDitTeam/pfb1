# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_sh_leave_attachment = fields.Boolean(
        "Enable Leave Attachment", implied_group='sh_all_in_one_hrms.group_enable_sh_leave_attachment')


class ShLeaveType(models.Model):
    _inherit = "hr.leave.type"

    sh_leave_attachment = fields.Boolean("Attachment", default=False)
    no_of_days = fields.Integer(string="No of Days")


class ShLeaveRequest(models.Model):
    _inherit = "hr.leave"

    sh_leave_req_attachment = fields.Binary("Attachment")
    leave_attach = fields.Boolean("leave attach", default=False)

    @api.onchange("number_of_days_display")
    def _onchange_(self):
        if self.holiday_status_id:
            if self.holiday_status_id.sh_leave_attachment:
                if self.number_of_days_display >= self.holiday_status_id.no_of_days:
                    self.leave_attach = True
                else:
                    self.leave_attach = False
