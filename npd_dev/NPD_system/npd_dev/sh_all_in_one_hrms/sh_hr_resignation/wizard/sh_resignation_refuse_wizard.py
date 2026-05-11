# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# Resignation refuse Wizard


class ShResignationRefuseWizard(models.Model):
    _name = 'sh.resignation.refuse.wizard'
    _description = 'Sh Resignation Refuse Wizard'

    ref_comment = fields.Text('Enter your Comment')

    def ref_action_ok(self):

        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        if active_id:
            resignation = self.env['sh.hr.resignation'].browse(active_id)
            resignation.write({
                'refused_comment': self.ref_comment,
                'refused_by': self.env.user.id,
                'state': 'refused',
            })

        template = self.env.ref(
            'sh_all_in_one_hrms.send_resignation_refused_notification_created_user')
        template.send_mail(active_id, force_send=True,
                           notif_layout='mail.mail_notification_light')
