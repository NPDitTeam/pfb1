# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError


class StockScrap(models.Model):
    _inherit = 'stock.scrap'
    
    branch_id = fields.Many2one('res.branch', string='Branch')
    
    
    @api.model 
    def default_get(self, field): 
        result = super(StockScrap, self).default_get(field)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result
    
    
    
    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        for obj in self:
            selected_brach = obj.branch_id
            if selected_brach:
                user_id = self.env['res.users'].browse(self.env.uid)
                user_branch = user_id.sudo().branch_id
                if user_branch and user_branch.id != selected_brach.id:
                    raise UserError("Please select active branch only. Other may create the Multi branch issue. \n\ne.g: If you wish to add other branch then Switch branch from the header and set that.") 

    
    
    def _prepare_move_values(self):
        res = super(StockScrap, self)._prepare_move_values()
        if self.branch_id:
            res['branch_id'] = self.branch_id.id
        return res
    
    
class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'
    
    branch_id = fields.Many2one('res.branch', string='Branch')
    
    
    @api.model 
    def default_get(self, fields): 
        result = super(StockMoveLine, self).default_get(fields)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result
    
    
