# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models, api
from datetime import datetime


class ProjectCustomChecklistTemplate(models.Model):
    _name = "project.custom.checklist.template"
    _description = "Project Custom Checklist Template"

    name = fields.Char("Name", required=True)
    checklist_template_ids = fields.Many2many('project.custom.checklist','checklist_template_ids_rel',
                                              string="Checklist Template")
