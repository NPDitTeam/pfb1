# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    branch_id = fields.Many2one(
        'res.branch',
        string='สาขา',
        help='สาขาที่เชื่อมโยงกับ Analytic Account นี้'
    )
