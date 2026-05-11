# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class Wizard_Rejected(models.TransientModel):
    _name = 'rejected_wizard'
    reason = fields.Text(string='Description', required=True)
    def confirm_reject(self):
        #pr_obj = self.env["purchase.request"]
        #print(" self._context.active_id..=", self.env.context.get("active_id"))
        #print(" self.reason.=", self.reason)
        pr_obj = self.env["purchase.request"].search([("id", "=", self.env.context.get("active_id"))])
        if pr_obj:
            pr_obj.mapped("line_ids").do_cancel()
            pr_obj.write({"state": "rejected"
            })
        else:    
            print("Not found")
        pr_obj.message_post(body="Reason for the rejection: " + self.reason)
        return

