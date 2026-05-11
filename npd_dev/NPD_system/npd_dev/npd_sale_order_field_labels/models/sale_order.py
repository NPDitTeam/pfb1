# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrderFieldLabels(models.Model):
    _inherit = 'sale.order'

    # เปลี่ยนชื่อ Sale Type เป็น ประเภทใบเสนอราคา
    pfb_so_type = fields.Selection(string='ประเภทใบเสนอราคา')

    # เปลี่ยนชื่อ Objective เป็น จุดประสงค์ในการเช่า
    pfb_objective_id = fields.Many2one(string='จุดประสงค์ในการเช่า')

    # เปลี่ยนชื่อ Day of Rent เป็น วันที่ต้องเช่า
    pfb_date_of_rent = fields.Integer(string='วันที่ต้องเช่า')

    # เปลี่ยนชื่อ Quotation เป็น เลขใบเสนอราคา
    quote_id = fields.Many2one(string='เลขใบเสนอราคา')

    # เปลี่ยนชื่อ Approver เป็น อนุมัติ
    approver_id = fields.Many2one(string='อนุมัติ')

    # เปลี่ยนชื่อ Delivery Date เป็น วันที่จัดส่ง
    commitment_date = fields.Datetime(string='วันที่จัดส่ง')


class SaleOrderLineFieldLabels(models.Model):
    _inherit = 'sale.order.line'

    product_uom_qty = fields.Float(string="จํานวนสินค้ารวม", store=True)

    # เปลี่ยนชื่อ Day of Rent เป็น จํานวนวันที่เช่า
    pfb_date_of_rent = fields.Integer(string='จํานวนวันที่เช่า')

    # เปลี่ยนชื่อ Quantity Rent เป็น จํานวนสินค้า
    pfb_quantity = fields.Integer(string='จํานวนสินค้า')

    # เปลี่ยนชื่อ Insurance เป็น ค่าประกัน
    pfb_insurance_price = fields.Float(string='ค่าประกัน')

    # เปลี่ยนชื่อ Secondary Qty เป็น น้ําหนักต่อหน่วย
    second_uom_qty = fields.Float(string='น้ําหนักต่อหน่วย')

    # เปลี่ยนชื่อ Discount Method เป็น ประเภทการลดราคา
    discount_method = fields.Selection(string='ประเภทการลดราคา')

    # เปลี่ยนชื่อ Discount Amount เป็น ยอดส่วนลด
    discount_amount = fields.Float(string='ยอดส่วนลด')

    # เปลี่ยนชื่อ Delivery Date เป็น วันที่จัดส่งสินค้า
    commitment_date = fields.Datetime(string='วันที่จัดส่งสินค้า')

    # เปลี่ยนชื่อ Subtotal without Discount เป็น ยอดหลังหักส่วนลด
    price_subtotal_without_discount = fields.Float(string='ยอดหลังหักส่วนลด')

    # เปลี่ยนชื่อ selection ประเภทส่วนลด - ส่วนลดสินค้า เป็น ส่วนลดราคาสินค้า
    discount_type_selection = fields.Selection(
        selection=[
            ('product', 'ส่วนลดราคาสินค้า'),
            ('rental', 'ส่วนลดค่าเช่า'),
        ],
        string='ประเภทส่วนลด'
    )
