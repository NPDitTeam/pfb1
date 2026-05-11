# Part of Softhealer Technologies.
from odoo import fields, models


class UpdatemassProject(models.TransientModel):
    _name = "sh.project.project.mass.update.wizard"
    _description = "Mass Update Wizard"

    project_project_ids = fields.Many2many('project.project')
    update_stage_bool = fields.Boolean(string="Update Stages")
    update_stages = fields.Many2many('project.task.type', string="Stages")

    update_method_stages = fields.Selection([
        ("add", "Add"),
        ("replace", "Replace"),
    ],
                                            default="add")

    def update_record(self):
        if self.update_method_stages == 'add':
            for i in self.update_stages:
                self.project_project_ids.write({'sh_stage_ids': [(4, i.id)]})

        if self.update_method_stages == 'replace':
            self.project_project_ids.write(
                {'sh_stage_ids': [(6, 0, self.update_stages.ids)]})
