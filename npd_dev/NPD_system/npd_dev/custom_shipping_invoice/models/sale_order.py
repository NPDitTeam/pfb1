from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import UserError, ValidationError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Fields provided by the user snippet, assuming they are defined elsewhere or added here
    shipping_invoice_id = fields.Many2one('account.move', string="Shipping Invoice")
    # shipping_cost และ shipping_cost_m ถูกกำหนดในโมดูลที่เกี่ยวข้องอยู่แล้ว (sale_order.py)
    start_rent_date = fields.Date(string="วันที่เริ่มต้นการเช่า", default=fields.Date.context_today)
    end_rent_date = fields.Date(string="วันที่สิ้นสุดการเช่า")

    def action_open_shipping_popup(self):
        """
        เปิด Popup สำหรับสร้าง Invoice ค่าขนส่ง
        โดยเลือกใช้ค่า: shipping_cost_m (ถ้า > 0) หรือ shipping_cost (ถ้า shipping_cost_m = 0)
        """
        self.ensure_one()

        # # 1. ตรวจสอบและดึงสินค้าค่าขนส่ง
        # shipping_product = self.env['product.product'].search([('default_code', '=', 'PR/00363')], limit=1)
        # if not shipping_product:
        #     raise models.ValidationError("ไม่พบสินค้าค่าขนส่ง รหัส PR/00363")
        #
        # # 2. **IMPLEMENTATION OF THE REQUESTED LOGIC**
        # # ตรวจสอบฟิลด์ shipping_cost_m: ถ้ามีค่าและ > 0 ให้ใช้ค่านั้น
        # final_shipping_cost = self.shipping_cost
        #
        # # ต้องเช็คว่ามีฟิลด์จริงก่อน (ป้องกัน Error หากฟิลด์ไม่ได้ถูกติดตั้งในโมดูล)
        # # และใช้เงื่อนไขว่าต้องมีค่ามากกว่า 0
        #
        # if hasattr(self, 'shipping_cost_m') and self.shipping_cost_m > 0:
        #     final_shipping_cost = self.shipping_cost_m
        #
        # _logger.info(f"Final shipping cost for popup: {final_shipping_cost} (SO: {self.name})")

        # 1️⃣ ตรวจสอบและดึงสินค้าค่าขนส่ง
        shipping_product = self.env['product.product'].search([('default_code', '=', 'PR/00363')], limit=1)
        if not shipping_product:
            raise models.ValidationError("ไม่พบสินค้าค่าขนส่ง รหัส PR/00363")

        # 2️⃣ เงื่อนไขการคำนวณ final_shipping_cost
        final_shipping_cost = 0.0  # ตั้งค่าเริ่มต้นป้องกัน error

        if self.use_special_delivery_zero and self.shipping_cost_m == 0:
            # ✅ ใช้ shipping_cost_m
            final_shipping_cost = self.shipping_cost_m

        elif not self.use_special_delivery_zero and self.shipping_cost_m > 0:
            # ✅ ใช้ shipping_cost_m
            final_shipping_cost = self.shipping_cost_m

        elif not self.use_special_delivery_zero and self.shipping_cost_m == 0:
            # ✅ ใช้ shipping_cost
            final_shipping_cost = self.shipping_cost

        else:
            # เงื่อนไข fallback ถ้าไม่เข้าเงื่อนไขใดเลย
            final_shipping_cost = self.shipping_cost

        _logger.info(f"Final shipping cost for popup: {final_shipping_cost} (SO: {self.name})")

        return {
            'name': 'สร้างใบค่าขนส่ง',
            'type': 'ir.actions.act_window',
            'res_model': 'popup.shipping.invoice',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_shipping_cost': final_shipping_cost,  # ใช้ค่าที่เลือกไว้
                'default_shipping_product_id': shipping_product.id
            }
        }

    def action_view_shipping_invoice(self):
        """ เปิดหน้าต่างดู Invoice ค่าขนส่ง """
        self.ensure_one()
        if self.shipping_invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.shipping_invoice_id.id,
                'target': 'current',
            }


class PopupShippingInvoice(models.TransientModel):
    _name = 'popup.shipping.invoice'
    _description = 'Popup for Creating Invoice with Shipping Cost'

    order_id = fields.Many2one('sale.order', string="Order")
    shipping_cost = fields.Float(string="Shipping Cost")
    shipping_product_id = fields.Many2one('product.product', string="Shipping Product")

    def _create_invoice(self):
        self.ensure_one()
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.order_id.partner_id.id,
            'invoice_origin': self.order_id.name,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.shipping_product_id.id,
                'name': self.shipping_product_id.name,
                'quantity': 1,
                'price_unit': self.shipping_cost,
                # ตั้งภาษีให้ถูกต้องตามบริบทของโมดูล (ในตัวอย่างนี้ไม่ได้กำหนด tax_ids)
            })],
        })
        self.order_id.write({'shipping_invoice_id': invoice.id})  # บันทึก Invoice ใน Sale Order
        return invoice

    def action_create_invoice(self):
        self._create_invoice()
        return {'type': 'ir.actions.act_window_close'}

    def action_create_view_invoice(self):
        invoice = self._create_invoice()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }
