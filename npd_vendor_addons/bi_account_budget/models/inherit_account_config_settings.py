# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields,models

class accountConfigSettings(models.TransientModel):
    _inherit = ['res.config.settings']

    partial_budget_approve = fields.Boolean(string='Partial Budget Approve',readonly=False)

    def get_values(self):
        res = super(accountConfigSettings, self).get_values()
        partial_budget_approve = self.env['ir.config_parameter'].sudo().get_param('bi_account_budget.partial_budget_approve')
        res.update(
            partial_budget_approve = partial_budget_approve,
        )
        return res

    def set_values(self):
        super(accountConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('bi_account_budget.partial_budget_approve', self.partial_budget_approve)



