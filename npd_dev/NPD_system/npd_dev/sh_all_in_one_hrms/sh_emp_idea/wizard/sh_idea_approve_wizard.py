# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh.idea approve Wizard


class ShIdeaApproveWizard(models.Model):
    _name = 'sh.idea.approve.wizard'
    _description = 'Sh Idea Approve Wizard'

    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'Minimum'),
        ('3', 'High'),
        ('4', 'Maximum'),
        ('5', 'Max'),
    ], string="Rating")
    app_comment = fields.Text('Enter your Comment')

    def action_ok(self):

        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        if active_id:
            idea = self.env['sh.idea'].browse(active_id)
            idea.write({
                'approved_comment': self.app_comment,
                'rating': self.priority,
                'approved_by': self.env.user.id,
            })

        template = self.env.ref(
            'sh_all_in_one_hrms.send_idea_approved_notification_created_user')
        template.send_mail(active_id, force_send=True,
                           notif_layout='mail.mail_notification_light')
