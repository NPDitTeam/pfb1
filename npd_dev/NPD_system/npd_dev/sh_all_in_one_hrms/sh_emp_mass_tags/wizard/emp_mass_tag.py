# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_hide_menu_emp_mass_tag = fields.Boolean(
        "Enable Employee Mass Tags", implied_group='sh_all_in_one_hrms.group_hide_menu_emp_mass_tag')


class ShEmpMassTagMultiAction(models.TransientModel):
    _name = 'sh.emp.mass.tag.multi.action'
    _description = 'Employee mass tag wizard for update tags by multi action'

    update_tag_type = fields.Selection([
        ('replace', 'Remove old tags and update new tags'),
        ('update', 'Keep old tags and update new tags'),
    ],
        default='replace',
        string='Update Type'
    )

    category_ids = fields.Many2many(
        comodel_name='hr.employee.category',
        relation="rel_sh_empmt_emp_mass_tag_hr_emp_categ",
        string='Tags'
    )

    employee_ids = fields.Many2many(
        comodel_name='hr.employee',
        relation="rel_sh_empmt_emp_mass_tag_hr_emp",
        string='Employees'
    )

    @api.model
    def default_get(self, fields):
        res = super(ShEmpMassTagMultiAction, self).default_get(fields)
        active_ids = self._context.get('active_ids')

        if active_ids:
            employees = self.env['hr.employee'].browse(active_ids)
            if employees:

                res.update({
                    'employee_ids': [(6, 0, employees.ids)]
                })

        return res

    def action_update_tags(self):
        if not self.env.user.has_group('sh_all_in_one_hrms.group_hide_menu_emp_mass_tag'):
            raise ValidationError(
                _("Enable Configuration for Employee Mass Tags"))

        else:
            if self.employee_ids:

                # remove all old tags and update new
                if self.update_tag_type == 'replace':
                    self.employee_ids.sudo().write({
                        'category_ids': [(6, 0, self.category_ids.ids)],
                    })

                # keep all old tags and update new
                if self.update_tag_type == 'update':
                    for employee in self.employee_ids:

                        # to make unique tag list.to avoid duplication of tags.
                        tag_list = employee.category_ids.ids

                        for tag in self.category_ids.ids:
                            if tag not in tag_list:
                                tag_list.append(tag)

                        # finally write unique tag list into employee
                        employee.sudo().write({
                            'category_ids': [(6, 0, tag_list)],
                        })

                # ODOO 14 FIRE ACTION TO UPDATE NEW CHANGE IN VIEW

                if not self._context.get('active_ids', False):
                    action = self.env.ref(
                        "hr.open_view_employee_list_my").read()[0]
                    return action
