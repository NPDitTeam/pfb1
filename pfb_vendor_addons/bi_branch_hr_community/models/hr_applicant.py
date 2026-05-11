# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _
from odoo.tools import pycompat


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    branch_id = fields.Many2one('res.branch', string='Branch')

    @api.model
    def default_get(self, flds):
        result = super(HrApplicant, self).default_get(flds)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result


    @api.onchange('job_id')
    def onchange_job_id(self):
        """ Override to get branch from department """
        department = self.env['hr.department'].browse(self.department_id.id)
        self.branch_id = department.branch_id
        
        
   