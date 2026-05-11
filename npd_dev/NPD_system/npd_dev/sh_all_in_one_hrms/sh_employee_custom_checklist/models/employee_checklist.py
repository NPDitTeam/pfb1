# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models, api
from datetime import datetime

class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_custom_check_list = fields.Boolean(
        "Enable Employee Custom Checklist", implied_group='sh_all_in_one_hrms.group_enable_custom_check_list')


class EmployeeEntryCustomChecklist(models.Model):
    _name = "employee.entry.custom.checklist"
    _description = "Employee Entry Custom Checklist"
    _order = "sequence,id desc"

    name = fields.Char("Name", required=True)
    sequence = fields.Integer(default=1)
    description = fields.Char("Description")
    company_id = fields.Many2one("res.company",
                                 string="Company",
                                 default=lambda self: self.env.company)


class EmployeeEntryCustomChecklistLine(models.Model):
    _name = "employee.entry.custom.checklist.line"
    _description = "Employee Entry Custom Checklist Line"
    _order = "id desc"

    name = fields.Many2one("employee.entry.custom.checklist",
                           "Name",
                           required=True)
    description = fields.Char("Description")
    updated_date = fields.Date("Date",
                               readonly=True,
                               default=datetime.now().date())
    state = fields.Selection([("new", "New"), ("completed", "Completed"),
                              ("cancelled", "Cancelled")],
                             string="State",
                             default="new",
                             readonly=True,
                             index=True)

    employee_id = fields.Many2one("hr.employee")

    def btn_check(self):
        for rec in self:
            rec.write({"state": "completed"})

    def btn_close(self):
        for rec in self:
            rec.write({"state": "cancelled"})

    @api.onchange("name")
    def onchange_custom_chacklist_name(self):
        self.description = self.name.description


class EmployeeExitCustomChecklist(models.Model):
    _name = "employee.exit.custom.checklist"
    _description = "Employee Exit Custom Checklist"
    _order = "sequence,id desc"

    name = fields.Char("Name", required=True)
    sequence = fields.Integer(default=1)
    description = fields.Char("Description")
    company_id = fields.Many2one("res.company",
                                 string="Company",
                                 default=lambda self: self.env.company)


class EmployeeExitCustomChecklistLine(models.Model):
    _name = "employee.exit.custom.checklist.line"
    _description = "Employee Exit Custom Checklist Line"
    _order = "id desc"

    name = fields.Many2one("employee.exit.custom.checklist",
                           "Name",
                           required=True)
    description = fields.Char("Description")
    updated_date = fields.Date("Date",
                               readonly=True,
                               default=datetime.now().date())
    state = fields.Selection([("new", "New"), ("completed", "Completed"),
                              ("cancelled", "Cancelled")],
                             string="State",
                             default="new",
                             readonly=True,
                             index=True)

    employee_id = fields.Many2one("hr.employee")

    def btn_check(self):
        for rec in self:
            rec.write({"state": "completed"})

    def btn_close(self):
        for rec in self:
            rec.write({"state": "cancelled"})

    @api.onchange("name")
    def onchange_custom_chacklist_name(self):
        self.description = self.name.description


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    entry_custom_checklist_ids = fields.Many2many(
        "employee.entry.custom.checklist", string="Entry Checklist")
    exit_custom_checklist_ids = fields.Many2many(
        "employee.exit.custom.checklist", string="Exit Checklist")

    entry_custom_checklist = fields.Float(
        " Checklist Completed", compute="_compute_entry_custom_checklist")
    exit_custom_checklist = fields.Float(
        " Checklist Completed ", compute="_compute_exit_custom_checklist")

    @api.depends("entry_custom_checklist_ids")
    def _compute_entry_custom_checklist(self):
        if self:
            for rec in self:
                total_cnt = self.env[
                    "employee.entry.custom.checklist.line"].search_count([
                        ("employee_id", "=", rec.id),
                        ("state", "!=", "cancelled")
                    ])
                compl_cnt = self.env[
                    "employee.entry.custom.checklist.line"].search_count([
                        ("employee_id", "=", rec.id),
                        ("state", "=", "completed")
                    ])

                if total_cnt > 0:
                    rec.entry_custom_checklist = (100.0 *
                                                  compl_cnt) / total_cnt
                else:
                    rec.entry_custom_checklist = 0

    entry_custom_checklist_ids = fields.One2many(
        "employee.entry.custom.checklist.line", "employee_id", "Checklist")
    entry_custom_checklist = fields.Float(
        " Checklist Completed  ", compute="_compute_entry_custom_checklist")

    @api.depends("exit_custom_checklist_ids")
    def _compute_exit_custom_checklist(self):
        if self:
            for rec in self:
                total_cnt = self.env[
                    "employee.exit.custom.checklist.line"].search_count([
                        ("employee_id", "=", rec.id),
                        ("state", "!=", "cancelled")
                    ])
                compl_cnt = self.env[
                    "employee.exit.custom.checklist.line"].search_count([
                        ("employee_id", "=", rec.id),
                        ("state", "=", "completed")
                    ])

                if total_cnt > 0:
                    rec.exit_custom_checklist = (100.0 * compl_cnt) / total_cnt
                else:
                    rec.exit_custom_checklist = 0

    exit_custom_checklist_ids = fields.One2many(
        "employee.exit.custom.checklist.line", "employee_id", "Checklist ")
    exit_custom_checklist = fields.Float(
        "  Checklist Completed ", compute="_compute_exit_custom_checklist")

    custom_checklist_entry_template_ids = fields.Many2many(
        comodel_name='employee.entry.custom.checklist.template',
        relation='custom_checklist_entry_template_table',
        string='CheckList Template')

    custom_checklist_exit_template_ids = fields.Many2many(
        comodel_name='employee.exit.custom.checklist.template',
        relation='custom_checklist_exit_template_table',
        string='CheckList Template ')

    @api.onchange('custom_checklist_entry_template_ids')
    def onchange_custom_checklist_entry_template_ids(self):
        update_ids = []
        for i in self.custom_checklist_entry_template_ids:
            for j in i._origin.entry_checklist_template:
                new_id = self.env[
                    "employee.entry.custom.checklist.line"].create({
                        'name':
                        j.id,
                        'description':
                        j.description
                    })
                update_ids.append(new_id.id)

        self.entry_custom_checklist_ids = [(6, 0, update_ids)]

    @api.onchange('custom_checklist_exit_template_ids')
    def onchange_custom_checklist_exit_template_ids(self):
        update_ids = []
        for i in self.custom_checklist_exit_template_ids:
            for j in i._origin.exit_checklist_template:
                new_id = self.env[
                    "employee.exit.custom.checklist.line"].create({
                        'name':
                        j.id,
                        'description':
                        j.description
                    })
                update_ids.append(new_id.id)

        self.exit_custom_checklist_ids = [(6, 0, update_ids)]
