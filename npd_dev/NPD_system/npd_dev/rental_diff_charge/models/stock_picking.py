# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockPickingRentalDiff(models.Model):
    _inherit = 'stock.picking'

    # ฟิลด์เก็บค่าเช่าส่วนต่าง (Boolean)
    # ค่าเริ่มต้น: ไม่ติ๊กถูก (False)
    collect_rental_diff = fields.Boolean(
        string='แสดงเก็บค่าเช่าส่วนต่าง',
        default=False,
        help='ติ๊กถูกหากต้องการเก็บค่าเช่าส่วนต่าง',
        copy=False,
        tracking=True
    )
