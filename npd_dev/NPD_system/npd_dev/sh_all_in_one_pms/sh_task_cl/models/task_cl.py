# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models, api


class TaskChecklist(models.Model):
    _name = "task.checklist"
    _description = 'Task Checklist'

    name = fields.Char("Name", required=True)
    description = fields.Char("Description")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company)


class ProjectTask(models.Model):
    _inherit = "project.task"

    @api.depends("checklist_ids")
    def _compute_checklist(self):
        if self:
            for data in self:
                total_cnt = data.env["task.checklist"].sudo().search_count([])

                comp_cnt = 0
                if data.checklist_ids:
                    for rec in data.sudo().checklist_ids:
                        if rec.name:
                            comp_cnt += 1

                    if total_cnt > 0:
                        data.checklist = (100.0 * comp_cnt) / total_cnt
                else:
                    data.checklist = 0

    checklist_ids = fields.Many2many("task.checklist", string="Checklist")
    checklist = fields.Float(
        "Checklist Completed",
        compute="_compute_checklist")
    check_bool_enable_task_check_list = fields.Boolean(
        related="company_id.enable_task_check_list")
