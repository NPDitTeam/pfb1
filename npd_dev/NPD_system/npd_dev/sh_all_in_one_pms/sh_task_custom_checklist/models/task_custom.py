# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models, api
from datetime import datetime


class TaskCustomChecklist(models.Model):
    _name = "task.custom.checklist"
    _description = 'Task Custom Checklist'
    _order = "id desc"

    name = fields.Char("Name", required=True)
    description = fields.Char("Description")


class TaskCustomChecklistLine(models.Model):
    _name = "task.custom.checklist.line"
    _description = "Task Custom Checklist Line"
    _order = "id desc"

    name = fields.Many2one("task.custom.checklist", "Name", required=True)
    description = fields.Char("Description")
    updated_date = fields.Date("Date",
                               readonly=True,
                               default=datetime.now().date())
    state = fields.Selection([('new', 'New'), ('completed', 'Completed'),
                              ('cancelled', 'Cancelled')],
                             string="State",
                             default='new',
                             readonly=True,
                             index=True)

    task_id = fields.Many2one("project.task")

    def btn_check(self):
        for rec in self:
            rec.write({'state': 'completed'})

    def btn_close(self):
        for rec in self:
            rec.write({'state': 'cancelled'})

    @api.onchange('name')
    def onchange_custom_chacklist_name(self):
        self.description = self.name.description


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.depends('custom_checklist_ids')
    def _compute_custom_checklist(self):
        if self:
            for rec in self:
                total_cnt = self.env[
                    'task.custom.checklist.line'].search_count([
                        ('task_id', '=', rec.id), ('state', '!=', 'cancelled')
                    ])
                compl_cnt = self.env[
                    'task.custom.checklist.line'].search_count([
                        ('task_id', '=', rec.id), ('state', '=', 'completed')
                    ])

                if total_cnt > 0:
                    rec.custom_checklist = (100.0 * compl_cnt) / total_cnt
                else:
                    rec.custom_checklist = 0

    custom_checklist_ids = fields.One2many("task.custom.checklist.line",
                                           "task_id",
                                           string="Checklist")
    custom_checklist = fields.Float("Checklist Completed",
                                    compute="_compute_custom_checklist")

    check_list = fields.Many2many('sh.task.checklist.template','check_list_rel',string="Check list")

    @api.onchange('check_list')
    def onchange_check_list(self):
        update_ids = []
        for i in self.check_list:
            for j in i._origin.checklist_ids:
                new_id = self.env["task.custom.checklist.line"].create({
                    'name':
                    j.id,
                    'description':
                    j.description
                })
                update_ids.append(new_id.id)

        self.custom_checklist_ids = [(6, 0, update_ids)]
