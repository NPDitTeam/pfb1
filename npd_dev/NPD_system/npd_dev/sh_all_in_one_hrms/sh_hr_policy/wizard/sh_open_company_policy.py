# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

# sh Ot reject Wizard


class ShCmpPolicyWizard(models.TransientModel):
    _name = 'sh.company.policy.wizard'
    _description = "Company Policy Wizard"

    company_id = fields.Many2one('res.company', string="Company")
    sh_policy = fields.Html(related='company_id.sh_policy')

    # def rej_action_ok(self):

    #     context = dict(self._context or {})
    #     active_id = context.get('active_id', False)
    #     if active_id:
    #         overtime = self.env['sh.hr.overtime'].browse(active_id)
    #         overtime.write({
    #             'reject_comment': self.rej_comment,
    #         })

    #     template = self.env.ref(
    #         'sh_all_in_one_hrms.send_overtime_request_reject_notification')
    #     template.sudo().send_mail(active_id, force_send=True,
    #                               email_layout_xmlid='mail.mail_notification_light')
