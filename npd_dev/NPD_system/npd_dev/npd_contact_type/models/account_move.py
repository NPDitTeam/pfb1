# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    contact_type = fields.Selection(
        selection=[
            ('branch', 'สาขา'),
            ('sale', 'Sales'),
        ],
        string='การติดต่อของลูกค้า',
        tracking=True,
        copy=True,
        help='ประเภทการติดต่อของลูกค้า ดึงมาจาก Sale Order',
    )

    sales_contact_id = fields.Many2one(
        'res.users',
        string='Sales ที่ติดต่อ',
        tracking=True,
        copy=True,
        help='Sales ที่ติดต่อลูกค้า ดึงมาจาก Sale Order',
    )
