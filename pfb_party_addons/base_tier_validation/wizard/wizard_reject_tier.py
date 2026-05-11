# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class Wizard_Rejected(models.TransientModel):
    _name = 'reject_tier_wizard'
    
    reason = fields.Text(string='Description', required=True)
    def confirm_reject(self):
        #pr_obj = self.env["purchase.request"].search([("id", "=", self.env.context.get("active_id"))])
        #if pr_obj:
            #pr_obj.mapped("line_ids").do_cancel()
            #pr_obj.write({"state": "rejected"
            #})
        #else:    
            #print("Not found")
        #pr_obj.message_post(body="Reason for rejection: " + self.reason)

        pr_obj = self.env["purchase.request"].search([("id", "=", self.env.context.get("active_id"))])
        pr_obj.ensure_one()
        sequences = pr_obj._get_sequences_to_approve(pr_obj.env.user)
        reviews = pr_obj.review_ids.filtered(lambda l: l.sequence in sequences)
        if pr_obj.has_comment:
            return pr_obj._add_comment("reject", reviews)
        pr_obj._rejected_tier(reviews)
        pr_obj._update_counter()
        pr_obj.message_post(body="Reason for the rejection: " + self.reason)

        return

