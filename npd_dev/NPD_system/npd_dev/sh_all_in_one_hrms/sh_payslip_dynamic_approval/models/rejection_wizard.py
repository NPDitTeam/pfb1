# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from datetime import datetime


class RejectionReasonWizard(models.TransientModel):
    _name = 'sh.reject.reason.wizard'

    name = fields.Char(string="Reason", required=True)

    def action_reject_payslip(self):

        active_obj = self.env[self.env.context.get('active_model')].browse(
            self.env.context.get('active_id'))
        active_obj.write({
            'reject_reason': self.name,
            'reject_by': active_obj.env.user.id,
            'rejection_date': datetime.now(),
            'state': 'cancel',
        })

        template_id = active_obj.env.ref(
            "sh_all_in_one_hrms.email_template_for_reject_hr_payslip")

        if template_id:
            template_id.sudo().send_mail(active_obj.id, force_send=True, email_values={
                'email_from': active_obj.env.user.email, 'email_to': active_obj.user_id.email})

        notifications = []
        if active_obj.user_id:
            notifications.append([
                (active_obj._cr.dbname, 'res.partner',
                 active_obj.user_id.partner_id.id),
                {'type': 'user_connection', 'title': _(
                    'Notitification'), 'message': 'Dear User!! The payslip %s you created has been rejected' % (active_obj.name), 'sticky': True, 'warning': True}])
            active_obj.env['bus.bus'].sendmany(notifications)
