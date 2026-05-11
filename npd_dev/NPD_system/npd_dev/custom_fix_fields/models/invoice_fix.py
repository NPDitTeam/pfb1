# -*- coding: utf-8 -*-
from odoo import models, fields


class InvoiceFix(models.Model):
    _inherit = 'account.move'

    # เพิ่มฟิลด์ที่ขาดหาย หรือเอกสารที่เกี่ยวข้อง
    custom_notes = fields.Text(
        string='Custom Notes',
        help='Additional custom notes for this document',
    )

    def write(self, vals):
        """Override write for invoice fixes"""
        result = super().write(vals)
        return result
