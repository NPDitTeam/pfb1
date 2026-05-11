# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models, api


class TaskCustomChecklist(models.Model):
    _name = "sh.task.checklist.template"
    _description = 'Task Checklist Template'

    name = fields.Char("Name", required=True)
    checklist_ids = fields.Many2many("task.custom.checklist",
                                     string="Check List")
