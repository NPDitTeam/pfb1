# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models, api


class ProjectTask(models.Model):
    _inherit = "project.task"

    test = fields.Char(string="Test")

    def action_mass_tag_update(self):
        return {
            'name':
            'Mass Update',
            'res_model':
            'sh.project.task.mass.update.wizard',
            'view_mode':
            'form',
            'context': {
                'default_project_task_ids':
                [(6, 0, self.env.context.get('active_ids'))]
            },
            'view_id':
            self.env.ref(
                'sh_all_in_one_pms.sh_project_task_update_wizard_form_view').
            id,
            'target':
            'new',
            'type':
            'ir.actions.act_window'
        }