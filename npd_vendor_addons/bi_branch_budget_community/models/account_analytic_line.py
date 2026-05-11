# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError



    
class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'
    _description = 'Analytic Line'
    
    
    branch_id = fields.Many2one('res.branch', related='account_id.branch_id', string='Branch', store=True)
    
    
    
  