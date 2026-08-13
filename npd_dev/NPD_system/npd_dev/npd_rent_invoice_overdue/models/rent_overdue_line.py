# -*- coding: utf-8 -*-
"""บรรทัดสรุปยอดค้างชำระ สำหรับแสดงในแท็บของใบสั่งเช่า

เป็น TransientModel เพราะข้อมูลคำนวณสดทุกครั้งที่เปิดฟอร์ม ไม่ต้องเก็บถาวร
(odoo มี cron เก็บกวาด transient ให้เองตาม transient_age_limit ใน odoo.conf)

มีไว้เพื่อให้พนักงานกดจากบรรทัด ไปเปิดใบสั่งเช่า/ใบแจ้งหนี้ใบนั้นได้ทันที
ตัวเลขทั้งหมดมาจาก sale.order.get_overdue_rent_data() ซึ่งเป็นตัวเดียวกับที่
ใช้พิมพ์ 'ใบกำกับการเช่าหนี้ค้างชำระ' -- ตัวเลขบนจอกับบนใบพิมพ์จึงตรงกันเสมอ
"""
from odoo import fields, models


class NpdRentOverdueLine(models.TransientModel):
    _name = 'npd.rent.overdue.line'
    _description = u'บรรทัดสรุปยอดค้างชำระของลูกค้า'
    _order = 'invoice_date, invoice_name'

    order_id = fields.Many2one(
        'sale.order', string=u'ใบสั่งเช่าที่กำลังเปิดอยู่',
        ondelete='cascade', index=True)

    sale_id = fields.Many2one('sale.order', string=u'เลขที่ใบสั่งเช่า', readonly=True)
    move_id = fields.Many2one('account.move', string=u'เลขที่ใบแจ้งหนี้', readonly=True)
    invoice_name = fields.Char(string=u'เลขที่ใบแจ้งหนี้', readonly=True)
    invoice_date = fields.Date(string=u'วันที่ใบแจ้งหนี้', readonly=True)
    pay_type = fields.Selection([
        ('not_paid', u'ค้างชำระเต็มจำนวน'),
        ('partial', u'ค้างชำระบางส่วน'),
    ], string=u'ประเภทค้างชำระ', readonly=True)
    doc_type = fields.Char(string=u'ประเภทการชำระ', readonly=True)
    amount_residual = fields.Monetary(
        string=u'ยอดค้างชำระ', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    return_state = fields.Selection([
        ('not_returned', u'ยังไม่คืน'),
        ('returned', u'คืนครบแล้ว'),
    ], string=u'สถานะการคืนของ', readonly=True,
        help=u'ยังไม่คืน = รายการสินค้าของใบนี้จะถูกดึงไปแสดงในใบกำกับด้วย\n'
             u'คืนครบแล้ว = ขึ้นเฉพาะยอดค้างชำระ ไม่ดึงสินค้า')

    def action_open_sale(self):
        """เปิดใบสั่งเช่าต้นทางของหนี้ก้อนนี้"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.sale_id.display_name,
            'res_model': 'sale.order',
            'res_id': self.sale_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_move(self):
        """เปิดใบแจ้งหนี้ใบนี้"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.move_id.display_name,
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
