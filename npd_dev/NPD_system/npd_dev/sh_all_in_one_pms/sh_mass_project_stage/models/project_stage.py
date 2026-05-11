# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models
from odoo.exceptions import ValidationError


class ProjectStage(models.Model):
    _inherit = "project.task.type"

    def action_mass_stage_update(self):
        parent_id = self.env.context.get("active_id")
        parent_model = self.env.context.get("active_model")
        parent_record = self.env[parent_model].browse(parent_id)
        check_boolean = parent_record.env.user.company_id.enable_mass_project_stage
        if check_boolean == True:
            return {
                'name':
                'Mass Update',
                'res_model':
                'sh.project.stage.mass.update.wizard',
                'view_mode':
                'form',
                'context': {
                    'default_project_task_ids':
                    [(6, 0, self.env.context.get('active_ids'))]
                },
                'view_id':
                self.env.ref(
                    'sh_all_in_one_pms.sh_project_stage_update_wizard_form_view'
                ).id,
                'target':
                'new',
                'type':
                'ir.actions.act_window'
            }

        else:
            raise ValidationError("Please Enable Mass Project Stage !")
