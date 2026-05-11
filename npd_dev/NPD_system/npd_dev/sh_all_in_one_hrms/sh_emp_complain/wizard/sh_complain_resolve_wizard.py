# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh.complain resolve Wizard


class ShComplainResolveWizard(models.Model):
    _name = 'sh.complain.resolve.wizard'
    _description = 'Sh Complain Resolve Wizard'

    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'Minimum'),
        ('3', 'High'),
        ('4', 'Maximum'),
        ('5', 'Max'),
    ], string="Rating")
    res_comment = fields.Text('Enter your Comment')

    def action_ok(self):

        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        if active_id:
            complain = self.env['sh.complain'].browse(active_id)
            complain.write({
                'resolved_comment': self.res_comment,
                'rating': self.priority,
                'resolved_by': self.env.user.id,
            })

        template = self.env.ref(
            'sh_all_in_one_hrms.send_complain_resolved_notification_created_user')
        template.send_mail(active_id, force_send=True,
                           notif_layout='mail.mail_notification_light')
