# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_reservation_quotation = fields.Boolean(
        string='ใบเสนอราคาแบบจอง',
        default=False,
        help='ทำเครื่องหมายหากเป็นใบเสนอราคาแบบจอง'
    )

    def _prepare_invoice(self):
        """Override เพื่อส่งข้อมูลใบเสนอราคาแบบจองไปยัง Invoice"""
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals['is_from_reservation'] = self.is_reservation_quotation
        return invoice_vals