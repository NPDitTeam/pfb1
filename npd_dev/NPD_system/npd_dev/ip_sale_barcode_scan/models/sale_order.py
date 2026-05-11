# -*- coding: utf-8 -*-
from odoo import models, fields, _

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'barcodes.barcode_events_mixin']

    def on_barcode_scanned(self, barcode):
        """ ตรวจสอบสินค้าจาก Barcode และเพิ่มลงใน Sale Order """
        print(f"📡 Scanned Barcode: {barcode}")

        # ค้นหาสินค้าจากบาร์โค้ด
        product = self.env['product.product'].search([('barcode', '=', barcode)], limit=1)

        if not product:
            return {
                'warning': {
                    'title': _('Wrong barcode'),
                    'message': _('The barcode "%(barcode)s" doesn\'t correspond to a proper product.') % {'barcode': barcode}
                }
            }

        # ตรวจสอบว่าสินค้าซ้ำใน order_line หรือไม่
        order_line = self.order_line.filtered(lambda l: l.product_id.id == product.id)

        if order_line:
            # 🔄 เพิ่มจำนวน `pfb_quantity` ทีละ 1
            order_line[0].pfb_quantity += 1
            print(f"🔄 Increased pfb_quantity for {product.display_name} to {order_line[0].pfb_quantity}")
        else:
            # 📌 เพิ่มสินค้าใหม่ใน `order_line`
            product_name = product.display_name
            if product.description_sale:
                product_name += '\n' + product.description_sale

            order_line_id = self.order_line.new({
                'name': product_name,
                'product_id': product.id,
                'pfb_quantity': 1,
                'product_uom': product.uom_id.id,
                'price_unit': product.list_price,
            })
            order_line_id.product_id_change()
            self.order_line += order_line_id

            print(f"✅ Added New Product: {product.display_name} with pfb_quantity = 1")

        return {'success': True}
