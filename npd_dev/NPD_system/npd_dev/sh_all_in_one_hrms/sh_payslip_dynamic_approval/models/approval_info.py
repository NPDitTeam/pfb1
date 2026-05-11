# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_sh_payslip_dynamic_approval = fields.Boolean(
        "Enable Payslip Dynamic Approval", implied_group='sh_all_in_one_hrms.group_enable_sh_payslip_dynamic_approval')


class ApprovalInfo(models.Model):
    _name = 'sh.approval.info'
    _description = "Approval Information"

    level = fields.Integer(string="Approval Level")
    user_ids = fields.Many2many('res.users', string="Users")
    group_ids = fields.Many2many('res.groups', string="Groups")
    status = fields.Boolean(string="Status")
    approval_date = fields.Datetime(string="Approved Date")
    approved_by = fields.Many2one('res.users', string="Approved By")
    hr_payslip_id = fields.Many2one('hr.payslip')
