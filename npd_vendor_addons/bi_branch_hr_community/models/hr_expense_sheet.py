# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    branch_id = fields.Many2one('res.branch', string='Branch')  
    
    @api.model 
    def default_get(self, flds): 
        """ Override to get default branch from employee """
        result = super(HrExpenseSheet, self).default_get(flds)
        employee_id = self.env['hr.employee'].search([('user_id','=',self.env.uid)],limit=1)

        if employee_id :
            if employee_id.branch_id :
                
                result['branch_id'] = employee_id.branch_id.id
        return result

    @api.onchange('employee_id')
    def get_branch(self):
        if self.employee_id:
            if self.employee_id.branch_id:
                self.update({'branch_id':self.employee_id.branch_id})
            else:
                self.update({'branch_id': False})    



