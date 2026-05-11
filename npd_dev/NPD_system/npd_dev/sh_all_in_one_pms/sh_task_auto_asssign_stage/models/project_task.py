# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models, api

class ProjectTaskType(models.Model):

    _inherit = 'project.task.type'

    assign_to = fields.Many2one('res.users', "Assign To")
    assign_multi_user_ids = fields.Many2many("res.users",
                                             string="Assign Multi User")

class ProjectType(models.Model):
    _inherit = "project.task"

    @api.onchange('stage_id')
    def onchange_stage_id(self):

        if self.stage_id.assign_to:
            self.user_id = self.stage_id.assign_to

        if self.sh_multi_user == True:
            self.sh_user_ids = self.stage_id.assign_multi_user_ids
