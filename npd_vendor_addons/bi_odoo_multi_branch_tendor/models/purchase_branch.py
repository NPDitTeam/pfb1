# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools import pycompat
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.exceptions import UserError

class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    branch_id = fields.Many2one('res.branch', string='Branch')  
    
    @api.model 
    def default_get(self, flds): 
        result = super(PurchaseRequisition, self).default_get(flds)
        user_obj = self.env['res.users']
        branch_id = self.env.user.branch_id.id
        result['branch_id'] = branch_id
        return result  
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
