# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, tools

class AccountsAsset(models.Model):
    _inherit = "account.asset.asset"

    branch_id = fields.Many2one('res.branch', string='Branch')

    @api.model 
    def default_get(self, field): 
        result = super(AccountsAsset, self).default_get(field)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result

class AccountAssetDepreciationLine(models.Model):
    _inherit = 'account.asset.depreciation.line'
    
    def create_move(self, post_move=True):
        res = super(AccountAssetDepreciationLine, self).create_move()
        for rec in self:
            if rec.asset_id.branch_id:
                if rec.move_id:
                    rec.move_id.write({'branch_id':rec.asset_id.branch_id.id})
                    for move_line in rec.move_id.line_ids:
                        move_line.write({'branch_id':rec.asset_id.branch_id.id})
        return res    