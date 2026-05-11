# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh.complain refuse Wizard


class ShComplainRefuseWizard(models.Model):
    _name = 'sh.complain.refuse.wizard'
    _description = 'Sh Complain Refuse Wizard'

    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'Minimum'),
        ('3', 'High'),
        ('4', 'Maximum'),
        ('5', 'Max'),
    ], string="Rating")
    ref_comment = fields.Text('Enter your Comment')

    def ref_action_ok(self):

        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        if active_id:
            complain = self.env['sh.complain'].browse(active_id)
            complain.write({
                'refused_comment': self.ref_comment,
                'rating': self.priority,
                'refused_by': self.env.user.id,
            })

        template = self.env.ref(
            'sh_all_in_one_hrms.send_complain_refused_notification_created_user')
        template.send_mail(active_id, force_send=True,
                           notif_layout='mail.mail_notification_light')
