# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh.resignation Approve Wizard


class ShResignationApprovedWizard(models.Model):
    _name = 'sh.resignation.approve.wizard'
    _description = 'Sh Resignation Approve Wizard'

    res_comment = fields.Text('Enter your Comment')

    def action_ok(self):

        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        if active_id:
            resignation = self.env['sh.hr.resignation'].browse(active_id)
            resignation.write({
                'approved_comment': self.res_comment,
                'approved_by': self.env.user.id,
                'state': 'approve',
            })

        template = self.env.ref(
            'sh_all_in_one_hrms.send_resignation_approved_notification_created_user')
        template.send_mail(active_id, force_send=True,
                           notif_layout='mail.mail_notification_light')
