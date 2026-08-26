# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .head_office_branch_common import compute_head_office_branch


class AccountVoucher(models.Model):
    """เมนู การรับ - ใช้เฉพาะเอกสารที่ check_type_show_selection = False"""

    _inherit = 'account.voucher'

    head_office_branch_id = fields.Many2one(
        'res.branch',
        string='สาขาสำนักงานใหญ่',
        compute='_compute_head_office_branch_id',
        store=True,
        readonly=True,
        help='เติมอัตโนมัติจากเมนู การกำหนดค่า > กำหนดค่าสาขา (สำนักงานใหญ่)\n'
             'ใช้เฉพาะเอกสารในเมนู การรับ (check_type_show_selection = False)',
    )

    @api.depends('branch_id', 'company_id', 'check_type_show_selection')
    def _compute_head_office_branch_id(self):
        compute_head_office_branch(
            self, 'voucher',
            applicable=lambda voucher: voucher.check_type_show_selection != 'true',
        )
