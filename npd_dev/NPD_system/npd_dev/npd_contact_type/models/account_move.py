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
        readonly=True,  # ✅ ล็อก: ดึงจาก Sale Order เท่านั้น กันพนักงานแก้ (ORM/_create_invoices ยัง set ได้)
        help='ประเภทการติดต่อของลูกค้า ดึงมาจาก Sale Order (อ่านอย่างเดียว)',
    )

    sales_contact_id = fields.Many2one(
        'res.users',
        string='Sales ที่ติดต่อ',
        tracking=True,
        copy=True,
        readonly=True,  # ✅ ล็อก: ดึงจาก Sale Order เท่านั้น กันพนักงานแก้ (ORM/_create_invoices ยัง set ได้)
        help='Sales ที่ติดต่อลูกค้า ดึงมาจาก Sale Order (อ่านอย่างเดียว)',
    )
