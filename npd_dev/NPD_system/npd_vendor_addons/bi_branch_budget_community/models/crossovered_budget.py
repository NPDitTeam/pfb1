# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError


class CrossoveredBudget(models.Model):
    _inherit = "crossovered.budget"
    _description = "Budget"


    @api.model 
    def default_get(self, field): 
        result = super(CrossoveredBudget, self).default_get(field)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result

    branch_id = fields.Many2one('res.branch', string='Branch')
    
    
        
    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        for obj in self:
            selected_brach = obj.branch_id
            if selected_brach:
                user_id = self.env['res.users'].browse(self.env.uid)
                user_branch = user_id.sudo().branch_id
                if user_branch and user_branch.id != selected_brach.id:
                    raise UserError("Please select active branch only. Other may create the Multi branch issue. \n\ne.g: If you wish to add other branch then Switch branch from the header and set that.") 

    
    

