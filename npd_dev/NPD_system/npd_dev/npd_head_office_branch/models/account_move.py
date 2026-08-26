# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .head_office_branch_common import BILL_MOVE_TYPES, compute_head_office_branch


class AccountMove(models.Model):
    """เมนู บิล ผู้ขาย"""

    _inherit = 'account.move'

    head_office_branch_id = fields.Many2one(
        'res.branch',
        string='สาขาสำนักงานใหญ่',
        compute='_compute_head_office_branch_id',
        store=True,
        readonly=True,
        help='เติมอัตโนมัติจากเมนู การกำหนดค่า > กำหนดค่าสาขา (สำนักงานใหญ่)',
    )

    @api.depends('branch_id', 'company_id', 'move_type')
    def _compute_head_office_branch_id(self):
        compute_head_office_branch(
            self, 'bill',
            applicable=lambda move: move.move_type in BILL_MOVE_TYPES,
        )
