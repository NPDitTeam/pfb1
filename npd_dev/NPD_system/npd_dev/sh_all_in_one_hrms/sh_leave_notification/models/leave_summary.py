# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields


class ShLeaveSummary(models.Model):
    _name = 'sh.leave.summary'
    _description = "Sh Leave Summary"
    
    leave_ids = fields.Many2many("hr.leave", string='Leaves')
    start_date = fields.Datetime("Start Date")
    end_date = fields.Datetime("End Date")
    employee_id = fields.Many2one("hr.employee", "Employee")
                                                                