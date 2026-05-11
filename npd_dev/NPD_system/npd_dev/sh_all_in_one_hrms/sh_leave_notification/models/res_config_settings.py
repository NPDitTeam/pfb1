# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sh_automatic_leave = fields.Selection([('weekly', 'Weekly'), ('monthly', 'Monthly'), ('both', 'Both')],
                                          string="Automatic leave Summary")
    
    sh_enable_automatic_leave = fields.Boolean(string="Enable Automatic leave Summary")

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sh_automatic_leave = fields.Selection(default=lambda self: self.env.user.company_id.sh_automatic_leave,
                                          string="Automatic leave Summary", related="company_id.sh_automatic_leave", readonly=False)
    
    sh_enable_automatic_leave = fields.Boolean(string="Enable Automatic leave Summary", related="company_id.sh_enable_automatic_leave", readonly=False)
    
    group_enable_emp_leave_notification = fields.Boolean(
        "Enable Employee Leave Notification", implied_group='sh_all_in_one_hrms.group_enable_emp_leave_notification')
