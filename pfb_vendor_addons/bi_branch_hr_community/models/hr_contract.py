# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _
from odoo.tools import pycompat


class HrContract(models.Model):
    _inherit = 'hr.contract'

    branch_id = fields.Many2one('res.branch', string='Branch') 
    
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.branch_id = self.employee_id.branch_id