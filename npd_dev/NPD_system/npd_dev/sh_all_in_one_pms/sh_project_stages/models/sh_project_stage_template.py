# Part of Softhealer Technologies.
from odoo import fields, models


class UpdatemassProject(models.Model):
    _name = "sh.project.stage.template"
    _description = "Project Task Template"

    name = fields.Char(required=True)
    stage_ids = fields.Many2many('project.task.type',
                                 string="Stages",
                                 required=True)
