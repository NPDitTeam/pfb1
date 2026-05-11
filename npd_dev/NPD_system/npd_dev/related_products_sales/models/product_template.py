from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # related_products_ids = fields.Many2many(
    #     'product.template',
    #     'product_template_rel',
    #     'src_id',
    #     'dest_id',
    #     string='Related Products',
    #     store=True,
    # )

    # def update_product_type(self):
    #     products = self.search([])
    #     for product in products:
    #         # Clear the route_ids field first
    #         product.route_ids = [(5, 0, 0)]
    #
    #         # Logic to add specific routes based on the product type
    #         if product.type == 'product':  # If the product is a storable product
    #             # Add specific routes for storable products
    #             routes = self.env['stock.location.route'].search([('product_selectable', '=', True)])
    #             product.route_ids = [(6, 0, routes.ids)]
    #
    #         elif product.type == 'consu':  # If the product is a consumable product
    #             # Add specific routes for consumable products
    #             routes = self.env['stock.location.route'].search(
    #                 [('product_selectable', '=', True), ('is_consumable', '=', True)])
    #             product.route_ids = [(6, 0, routes.ids)]
    #
    #         elif product.type == 'service':  # If the product is a service
    #             # Add specific routes for service products
    #             routes = self.env['stock.location.route'].search(
    #                 [('product_selectable', '=', True), ('is_service', '=', True)])
    #             product.route_ids = [(6, 0, routes.ids)]
    def update_product_type(self):
        sale_orders = self.env['sale.order'].sudo().search([])
        for lo in sale_orders:
            lo.date_order_x = lo.date_order
    # def update_product_type(self):
    #     cr = self.env.cr
    #
    #     # อัปเดตจาก stock.inventory.line (ข้อมูลล่าสุดตาม product_id + location_id)
    #     cr.execute("""
    #         WITH latest_inventory AS (
    #             SELECT DISTINCT ON (product_id, location_id)
    #                 product_id,
    #                 location_id,
    #                 product_qty
    #             FROM stock_inventory_line
    #             ORDER BY product_id, location_id, create_date DESC
    #         )
    #         UPDATE stock_quant q
    #         SET stock_initial = l.product_qty
    #         FROM latest_inventory l
    #         WHERE q.product_id = l.product_id
    #           AND q.location_id = l.location_id
    #     """)
    #     print("✅ ขั้นตอนที่ 1: อัปเดตจาก stock.inventory.line เรียบร้อย")
    #
    #     # อัปเดตแถวที่ยังไม่มีค่า (stock_initial IS NULL) ด้วยค่าจาก quantity ที่มีอยู่ปัจจุบัน
    #     cr.execute("""
    #         UPDATE stock_quant
    #         SET stock_initial = quantity
    #         WHERE stock_initial IS NULL
    #     """)
    #     print("✅ ขั้นตอนที่ 2: อัปเดต fallback จาก quantity สำเร็จ")
    #
    #     print("🎯 อัปเดต stock_initial ทั้งหมดเรียบร้อยแล้ว")

    # def update_product_type(self):
    #     products = self.search([('name', 'like', '%(R)')])
    #     # print('*******************',roduct_count)
    #     # products = self.search([('name', 'like', '%(S)')])
    #     for product in products:
    #         # product.type = 'product'
    #         # product.sale_ok = 'false'
    #         # product.pfb_rent_ok = 'true'
    #         # product.weight = 1
    #         # product.allow_negative_stock = 'true'
    #         # product.invoice_policy = 'order'
    #         # producct.invoice_policy = 'order'
    #           product.taxes_id = [(6, 0, [21])]

        # p_roducts = self.search([('default_code', 'not in', ['', False])])
        #
        # for produc_t in p_roducts:
        #     produc_t.barcode = produc_t.default_code

    # def update_product_type(self):
    #     products = self.search([('type', '=', 'product')])
    #     for product in products:
    #         product.invoice_policy = 'order'


    # def update_product_type(self):
    #     # ค้นหาสินค้าที่มี default_code 9 หลัก
    #     products = self.search([('type', '=', 'product')])
    #     for product in products:
    #         if len(product.default_code) == 9:
    #             new_code = '0' + product.default_code
    #
    #             # ตรวจสอบว่ามีสินค้ารหัสนี้ในระบบหรือไม่
    #             existing_product = self.search([('default_code', '=', new_code)])
    #             if not existing_product:
    #                 product.default_code = new_code
    #                 print('Updated default_code for product:', product.default_code)
    #             else:
    #                 # ข้ามการอัปเดตถ้าพบว่ารหัสนี้ซ้ำ
    #                 print('Skipped update for product:', product.default_code, '- Duplicate code found:', new_code)

    # @api.depends('related_products_ids')
    # def _compute_related_product_names(self):
    #     for product in self:
    #         print('product.related_products_ids', product.related_products_ids)
    #
    # related_product_names = fields.Char(string='Related Product Names', compute='_compute_related_product_names',
    #                                     store=True)


# class SaleOrderLine(models.Model):
#     _inherit = 'sale.order.line'
#
#     @api.model
#     def create(self, values):
#         line = super(SaleOrderLine, self).create(values)
#
#         if 'product_id' in values and 'order_id' in values:
#             product_id = values['product_id']
#             order_id = values['order_id']
#             order = self.env['sale.order'].browse(order_id)
#
#             related_products_check = self.env['product.product'].search(
#                 [('id', '=', product_id)])
#
#             related_products = self.env['product.product'].search(
#                 [('product_tmpl_id', '=', related_products_check.related_products_ids.ids)])
#
#             new_lines = self.env['sale.order.line']
#             for related_product in related_products:
#
#                 new_line = self.env['sale.order.line'].create({
#                     'order_id': order_id,
#                     'product_id': related_product.id,
#
#                 })
#                 new_lines += new_line
#
#             order.write({'order_line': [(4, line.id) for line in new_lines]})
#
#         return line
