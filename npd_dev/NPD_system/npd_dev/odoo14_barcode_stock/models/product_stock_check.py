from odoo import models, fields, api

class ProductStockCheck(models.TransientModel):
    _name = 'product.stock.check'
    _description = 'ตรวจสอบสต็อกสินค้าด้วยบาร์โค้ด'

    barcode = fields.Char(string='บาร์โค้ด')
    product_id = fields.Many2one('product.product', string='สินค้า', domain=[('barcode', '!=', False)])
    quantity_on_hand = fields.Float(string='จำนวนคงเหลือ', readonly=True)

    @api.depends('barcode', 'product_id')
    @api.onchange('barcode', 'product_id')
    def _onchange_product(self):
        if self.barcode:
            product = self.env['product.product'].search([('barcode', '=', self.barcode)], limit=1)
            if product:
                self.product_id = product.id
                self.quantity_on_hand = product.qty_available
        elif self.product_id:
            self.quantity_on_hand = self.product_id.qty_available

class SaleConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    show_product_stock_menu = fields.Boolean(string='เปิดใช้งานการตรวจสอบสต็อกสินค้า')

class ProductStockMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def create(self, vals):
        menu = super(ProductStockMenu, self).create(vals)
        if vals.get('name') == 'ตรวจสอบสต็อกสินค้า' and self.env.user.has_group('base.group_system'):
            menu.write({'active': True})
        return menu
