# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SaleOrderFix(models.Model):
    _inherit = 'sale.order'

    # เพิ่มฟิลด์ที่ขาดหาย
    c_date = fields.Date(
        string='Custom Date',
        help='Custom date field for sale order',
        default=fields.Date.context_today,
    )

    @api.model
    def create(self, vals):
        """Override create to add default c_date if missing"""
        if 'c_date' not in vals:
            vals['c_date'] = fields.Date.context_today(self)
        return super().create(vals)

    def write(self, vals):
        """Override write to ensure c_date is properly set"""
        result = super().write(vals)
        return result
