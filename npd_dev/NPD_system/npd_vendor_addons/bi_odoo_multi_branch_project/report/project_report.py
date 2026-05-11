# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools


class ReportProjectTaskUser(models.Model):
    _inherit = "report.project.task.user"

    branch_id = fields.Many2one('res.branch', string='Branch')
    
    def _select(self):

        return super(ReportProjectTaskUser, self)._select() + ", t.branch_id  as branch_id"

    def _group_by(self):

        return super(ReportProjectTaskUser, self)._group_by() + ", t.branch_id"
