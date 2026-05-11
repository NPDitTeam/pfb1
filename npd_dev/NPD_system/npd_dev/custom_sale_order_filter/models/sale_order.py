from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'  # ✅ ใช้ list ในการสืบทอดหลายคลาส

    date_order_x = fields.Date(  # ✅ ฟิลด์ใหม่ที่ถูกต้อง
        string="วันที่สั่งซื้อ",
        compute='_compute_date_order_x',
        store=True
    )

    @api.depends('date_order')  # ✅ ระบุ dependency ให้ compute รู้ว่าต้องทำงานเมื่อ date_order เปลี่ยน
    def _compute_date_order_x(self):
        for record in self:
            record.date_order_x = record.date_order
