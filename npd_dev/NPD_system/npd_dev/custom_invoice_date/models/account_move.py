# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ฟิลด์สำหรับเช็คว่าผู้ใช้สามารถแก้ไขวันที่ได้หรือไม่
    can_edit_invoice_date = fields.Boolean(
        string='สามารถแก้ไขวันที่ Invoice',
        compute='_compute_can_edit_invoice_date',
        store=False
    )

    # ฟิลด์สำหรับเก็บว่ามาจากใบเสนอราคาแบบจองหรือไม่
    is_from_reservation = fields.Boolean(
        string='มาจากใบเสนอราคาแบบจอง',
        compute='_compute_is_from_reservation',
        store=False
    )

    @api.depends('invoice_origin')
    def _compute_is_from_reservation(self):
        """คำนวณว่า Invoice มาจากใบเสนอราคาแบบจองหรือไม่"""
        for move in self:
            move.is_from_reservation = False
            if move.invoice_origin:
                # ค้นหา Sale Order จาก invoice_origin
                sale_order = self.env['sale.order'].search([
                    ('name', '=', move.invoice_origin)
                ], limit=1)

                if sale_order:
                    move.is_from_reservation = sale_order.is_reservation_quotation

    @api.depends('invoice_origin')
    def _compute_can_edit_invoice_date(self):
        """คำนวณว่าผู้ใช้ปัจจุบันสามารถแก้ไขวันที่ได้หรือไม่"""
        for move in self:
            user = self.env.user
            # ถ้าผู้ใช้มีสิทธิ์ หรือเป็น Invoice ที่สร้างโดยตรง (ไม่มี invoice_origin)
            if hasattr(user, 'allow_edit_invoice_date'):
                move.can_edit_invoice_date = user.allow_edit_invoice_date or not move.invoice_origin
            else:
                # ถ้าไม่มี field allow_edit_invoice_date ให้แก้ไขได้เสมอถ้าไม่มี origin
                move.can_edit_invoice_date = not move.invoice_origin