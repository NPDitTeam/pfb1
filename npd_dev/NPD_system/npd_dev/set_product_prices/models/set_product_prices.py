from odoo import models, fields, api
from odoo.exceptions import UserError

class ProductTemplatePrice(models.Model):
    _inherit = "product.template"

    high_price = fields.Float(string='High Price')
    low_price = fields.Float(string='Low Price')

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('price_unit')
    def _check_price_limits(self):
        for line in self:
            product = line.product_id.product_tmpl_id
            if product:
                tolerance = 1e-9  # กำหนดค่าความคลาดเคลื่อนในการเปรียบเทียบ
                if product.high_price != 0 and line.price_unit > product.high_price + tolerance:
                    raise UserError(
                        f"ราคาของสินค้าจะต้องไม่เกินหรือเท่ากับ {product.high_price} บาท")
                if product.low_price != 0 and line.price_unit < product.low_price - tolerance:
                    raise UserError(
                        f"ราคาของสินค้าจะต้องไม่น้อยกว่าหรือเท่ากับ {product.low_price} บาท")
