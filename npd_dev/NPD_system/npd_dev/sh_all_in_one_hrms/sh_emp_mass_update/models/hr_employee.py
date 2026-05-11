# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, _
from odoo.exceptions import ValidationError

class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_mass_update = fields.Boolean(
        "Enable Employee Mass Update Manager", implied_group='sh_all_in_one_hrms.group_enable_mass_update')


class AccountInvoice(models.Model):
    _inherit = "hr.employee"

    def action_manager_mass_tag_update(self):

        if self.env.user.has_group('hr.group_hr_manager'):
            return {
                'name':
                'Mass Update',
                'res_model':
                'sh.employee.manager.update.mass.tag.wizard',
                'view_mode':
                'form',
                'context': {
                    'default_all_hr_employee_ids':
                    [(6, 0, self.env.context.get('active_ids'))]
                },
                'view_id':
                self.env.ref(
                    'sh_all_in_one_hrms.sh_employee_manager_mass_tag_wizard_form_view'
                ).id,
                'target':
                'new',
                'type':
                'ir.actions.act_window'
            }
        else:
            raise ValidationError(_("You are not authorized to perform this !"))
