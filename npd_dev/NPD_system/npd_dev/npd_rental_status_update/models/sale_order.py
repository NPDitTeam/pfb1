# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    # ไม่จำเป็นต้องมี method เพิ่มเติม เพราะย้าย logic ไปที่ wizard แล้ว
