# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models, api
from datetime import datetime


class ProjectCustomChecklist(models.Model):
    _name = "project.custom.checklist"
    _description = "Project Custom Checklist"
    _order = "id desc"

    name = fields.Char("Name", required=True)
    description = fields.Char("Description")
    company_id = fields.Many2one("res.company",
                                 string="Company",
                                 default=lambda self: self.env.company)


class ProjectCustomChecklistLine(models.Model):
    _name = "project.custom.checklist.line"
    _description = "Project Custom Checklist Line"
    _order = "id desc"

    name = fields.Many2one("project.custom.checklist", "Name", required=True)
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

    project_id = fields.Many2one("project.project")

    def btn_check(self):
        for rec in self:
            rec.write({"state": "completed"})

    def btn_close(self):
        for rec in self:
            rec.write({"state": "cancelled"})

    @api.onchange("name")
    def onchange_custom_chacklist_name(self):
        self.description = self.name.description


class ProjectProject(models.Model):
    _inherit = "project.project"

    @api.depends("custom_checklist_ids")
    def _compute_custom_checklist(self):
        for rec in self:
            total_cnt = self.env["project.custom.checklist.line"].search_count(
                [("project_id", "=", rec.id), ("state", "!=", "cancelled")])
            compl_cnt = self.env["project.custom.checklist.line"].search_count(
                [("project_id", "=", rec.id), ("state", "=", "completed")])

            if total_cnt > 0:
                rec.custom_checklist = (100.0 * compl_cnt) / total_cnt
            else:
                rec.custom_checklist = 0

    custom_checklist_ids = fields.One2many("project.custom.checklist.line",
                                           "project_id", "Checklist")
    custom_checklist = fields.Float(" Checklist Completed ",
                                    compute="_compute_custom_checklist")

    checklsit_template = fields.Many2many("project.custom.checklist.template",'checklsit_template_rel',
                                          string="Checklist Template")

    @api.onchange('checklsit_template')
    def onchange_checklsit_template(self):
        update_ids = []
        for i in self.checklsit_template:
            for j in i._origin.checklist_template_ids:
                new_id = self.env["project.custom.checklist.line"].create({
                    'name':
                    j.id,
                    'description':
                    j.description
                })
                update_ids.append(new_id.id)

        self.custom_checklist_ids = [(6, 0, update_ids)]
