# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_sh_payslip_send_email = fields.Boolean(
        "Enable Payslip Send Email", implied_group='sh_all_in_one_hrms.group_enable_sh_payslip_send_email')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    send_payslip = fields.Boolean("Send Payslip in Email ?")


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip', 'mail.thread']

    def action_payslip_done(self):

        super(HrPayslip, self).action_payslip_done()

        if self.employee_id:
            if self.env.user.has_group('sh_all_in_one_hrms.group_enable_sh_payslip_send_email'):
                if self.employee_id.send_payslip:

                    if self.employee_id.work_email:
                        template = self.env.ref(
                            'sh_all_in_one_hrms.template_hr_employee_payslip_send_email')

                        if template:
                            template.send_mail(self.id, force_send=True)

    def send_payslip_email(self):

        self.ensure_one()

        ir_model_data = self.env['ir.model.data']
        if self.employee_id:

                if self.env.user.has_group('sh_all_in_one_hrms.group_enable_sh_payslip_send_email'):
                    if self.employee_id.send_payslip:

                        if self.employee_id.work_email:

                            try:
                                template_id = ir_model_data.get_object_reference(
                                    'sh_all_in_one_hrms', 'template_hr_employee_payslip_send_email')[1]
                            except ValueError:
                                template_id = False

                            try:
                                compose_form_id = ir_model_data.get_object_reference(
                                    'mail', 'email_compose_message_wizard_form')[1]
                            except ValueError:
                                compose_form_id = False
                            ctx = {
                                'default_model': 'hr.payslip',
                                'default_res_id': self.ids[0],
                                'default_use_template': bool(template_id),
                                'default_template_id': template_id,
                                'default_composition_mode': 'comment',
                                'force_email': True
                            }
                            return {
                                'type': 'ir.actions.act_window',
                                'view_mode': 'form',
                                'res_model': 'mail.compose.message',
                                'views': [(compose_form_id, 'form')],
                                'view_id': compose_form_id,
                                'target': 'new',
                                'context': ctx,
                            }
                    else:
                        raise UserError(
                            _("Please Enable Send Payslip ? Feature for this Employee!"))


class MassHrPayslipEmailSend(models.Model):
    _name = 'mass.hr.payslip.mail.send'
    _description = 'Send Payslip in Mail'

    def send_payslip_email_confirm(self):

        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['hr.payslip'].browse(active_ids):
            if record.employee_id:

                    if self.env.user.has_group('sh_all_in_one_hrms.group_enable_sh_payslip_send_email'):
                        if record.employee_id.send_payslip:

                            if record.employee_id.work_email:

                                template = self.env.ref(
                                    'sh_all_in_one_hrms.template_hr_employee_payslip_send_email')

                                if template.id:
                                    template.send_mail(
                                        record.id, force_send=True)
                        else:
                            raise UserError(
                                _("Please Enable Send Payslip ? Feature for Selected Employee!"))
        return {'type': 'ir.actions.act_window_close'}
