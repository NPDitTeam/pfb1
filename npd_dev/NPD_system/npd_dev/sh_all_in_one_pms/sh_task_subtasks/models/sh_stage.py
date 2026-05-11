# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo.exceptions import UserError, ValidationError

from odoo import fields, models, api


class TaskStage(models.Model):
    _inherit = "project.task.type"

    sh_done = fields.Boolean("Done")
    sh_cancel = fields.Boolean("Cancel")
    


class SubTask(models.Model):
    _inherit = "project.task"

    sh_sub_task_lines = fields.One2many("project.task", "parent_id",
                                        "Sub Task")

    check_bool_enable_task_sub_task = fields.Boolean(
        related="company_id.enable_task_sub_task")

    @api.onchange('stage_id')
    def Onchange(self):
        if self.stage_id.sh_done:
            sub_task = self.search([('parent_id', '=', self._origin.id)])
            for rec in sub_task:
                if rec.stage_id.sh_done == False:
                    raise UserError('Complete the sub task first')
        elif self.stage_id.sh_cancel == True:
            sub_task = self.search([('parent_id', '=', self._origin.id)])
            stage_id = self.env['project.task.type'].search(
                [('sh_cancel', '=', True)], limit=1)
            for rec in sub_task:
                rec.sudo().write({'stage_id': stage_id.id})
