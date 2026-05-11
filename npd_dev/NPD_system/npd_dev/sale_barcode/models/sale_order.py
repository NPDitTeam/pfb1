from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    barcode = fields.Char(
        string="Enter Barcode",
        help="Scan a barcode or enter manually"
    )

    def action_process_barcode(self):
        """เรียกฟังก์ชันนี้เมื่อกด Enter เพื่อเพิ่มสินค้า"""
        if not self.barcode:
            return {
                'warning': {
                    'title': 'No Barcode',
                    'message': 'Please enter or scan a barcode first.'
                }
            }

        self.add_product_by_barcode()
        self.barcode = False  # รีเซ็ต barcode หลังประมวลผล
        return True  # ส่งคืน True เพื่อบอกว่าเรียกสำเร็จ

    def add_product_by_barcode(self):
        """เพิ่มสินค้าลงใน Sale Order โดยอัตโนมัติเมื่อสแกนบาร์โค้ด"""
        for order in self:
            if not order.barcode:
                continue

            # ค้นหาสินค้าจากบาร์โค้ด
            product = self.env['product.product'].search([('barcode', '=', order.barcode)], limit=1)

            if not product:
                return {
                    'warning': {
                        'title': 'Product Not Found',
                        'message': f"No product found for barcode: {order.barcode}"
                    }
                }

            # ค้นหา order line ที่มีสินค้านี้อยู่แล้ว
            order_line = order.order_line.filtered(lambda l: l.product_id.id == product.id)

            if order_line:
                order_line[0].product_uom_qty += 1
            else:
                order.write({
                    'order_line': [(0, 0, {
                        'product_id': product.id,
                        'name': product.name,
                        'product_uom_qty': 1,
                        'price_unit': product.lst_price,
                    })]
                })