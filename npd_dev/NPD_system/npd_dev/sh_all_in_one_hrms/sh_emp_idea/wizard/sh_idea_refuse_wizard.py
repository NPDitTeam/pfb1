# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh.idea refuse Wizard


class ShIdeaRefuseWizard(models.Model):
    _name = 'sh.idea.refuse.wizard'
    _description = 'Sh Idea Refuse Wizard'

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
            idea = self.env['sh.idea'].browse(active_id)
            idea.write({
                'refused_comment': self.ref_comment,
                'rating': self.priority,
                'refused_by': self.env.user.id,
            })

        template = self.env.ref(
            'sh_all_in_one_hrms.send_idea_refused_notification_created_user')
        template.send_mail(active_id, force_send=True,
                           notif_layout='mail.mail_notification_light')
