# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models, api

class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_check_list = fields.Boolean(
        "Enable Employee Checklist", implied_group='sh_all_in_one_hrms.group_enable_check_list')

class EmployeeEntryChecklist(models.Model):
    _name = "employee.entry.checklist"
    _description = "Employee Entry Checklist"
    _order = "id desc"

    name = fields.Char("Name", required=True)
    description = fields.Char("Description")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company)


class EmployeeExitChecklist(models.Model):
    _name = "employee.exit.checklist"
    _description = "Employee Exit Checklist"
    _order = "id desc"

    name = fields.Char("Name", required=True)
    description = fields.Char("Description")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    entry_checklist_ids = fields.Many2many(
        "employee.entry.checklist",
        string="Entry Checklist")
    exit_checklist_ids = fields.Many2many(
        "employee.exit.checklist",
        string="Exit Checklist")

    entry_checklist = fields.Float(
        "Checklist Completed",
        compute="_compute_entry_checklist")
    exit_checklist = fields.Float(
        "Checklist Completed ",
        compute="_compute_exit_checklist")

    @api.depends("entry_checklist_ids")
    def _compute_entry_checklist(self):
        if self:
            for record in self:
                total_cnt = self.env["employee.entry.checklist"].sudo().search_count([
                ])
                comp_cnt = 0
                if record.entry_checklist_ids:
                    for rec in record.sudo().entry_checklist_ids:
                        if rec.name:
                            comp_cnt += 1

                    if total_cnt > 0:
                        record.entry_checklist = (100.0 * comp_cnt) / total_cnt
                else:
                    record.entry_checklist = 0

    @api.depends("exit_checklist_ids")
    def _compute_exit_checklist(self):
        if self:
            for record in self:
                total_cnt = self.env["employee.exit.checklist"].sudo().search_count([
                ])
                comp_cnt = 0
                if record.exit_checklist_ids:
                    for rec in record.sudo().exit_checklist_ids:

                        if rec.name:
                            comp_cnt += 1

                    if total_cnt > 0:
                        record.exit_checklist = (100.0 * comp_cnt) / total_cnt
                else:
                    record.exit_checklist = 0
