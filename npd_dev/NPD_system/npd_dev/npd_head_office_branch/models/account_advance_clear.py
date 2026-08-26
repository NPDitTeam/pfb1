# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .head_office_branch_common import compute_head_office_branch


class AccountAdvanceClear(models.Model):
    """เมนู Avance Clear"""

    _inherit = 'account.advance.clear'

    head_office_branch_id = fields.Many2one(
        'res.branch',
        string='สาขาสำนักงานใหญ่',
        compute='_compute_head_office_branch_id',
        store=True,
        readonly=True,
        help='เติมอัตโนมัติจากเมนู การกำหนดค่า > กำหนดค่าสาขา (สำนักงานใหญ่)',
    )

    @api.depends('branch_id', 'company_id')
    def _compute_head_office_branch_id(self):
        compute_head_office_branch(self, 'advance_clear')
