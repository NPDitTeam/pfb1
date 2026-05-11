# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    start_x_date = fields.Date(
        string='วันที่เริ่มต้นการเช่า',
        help='วันที่เริ่มต้นการเช่าสินค้า',
        readonly=False,
        copy=False
    )

    end_x_date = fields.Date(
        string='วันที่สิ้นสุดการเช่า',
        help='วันที่สิ้นสุดการเช่าสินค้า',
        readonly=False,
        copy=False
    )
    
    # ✅ เพิ่มฟิลด์วันที่คืน
    return_date = fields.Datetime(
        string='วันที่และเวลาคืน',
        help='วันที่และเวลาคืนสินค้า',
        default=lambda self: fields.Datetime.now(),
        copy=False,
        tracking=True
    )
    
    # ✅ Computed field สำหรับควบคุม readonly ของ return_date
    is_return_date_readonly = fields.Boolean(
        string='Return Date is Readonly',
        compute='_compute_is_return_date_readonly',
        help='ตรวจสอบว่าผู้ใช้สามารถแก้ไขวันที่คืนได้หรือไม่'
    )
    
    @api.depends('create_uid')
    def _compute_is_return_date_readonly(self):
        """คำนวณว่าผู้ใช้สามารถแก้ไขวันที่คืนได้หรือไม่"""
        for rec in self:
            # ถ้าผู้ใช้ติ๊ก can_edit_force_date = True → readonly = False (แก้ไขได้)
            # ถ้าไม่ติ๊ก = False → readonly = True (แก้ไขไม่ได้)
            rec.is_return_date_readonly = not rec.env.user.can_edit_force_date