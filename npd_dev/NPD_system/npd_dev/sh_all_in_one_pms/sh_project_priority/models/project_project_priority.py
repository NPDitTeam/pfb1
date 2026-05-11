# Part of Softhealer Technologies.
from odoo import models, fields


class ProjectProject(models.Model):
    _inherit = "project.project"

    sh_priority = fields.Selection([('0', 'Low'), ('1', 'Medium'),
                                    ('2', 'High'), ('3', 'Very High')],
                                   string="Priority")
    default_added_to_task = fields.Boolean()

    check_bool_project_priority = fields.Boolean(
        related="company_id.enable_project_priority")
