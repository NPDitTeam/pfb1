from odoo import models, fields, api


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    price_before_vat = fields.Float(
        string='ราคาก่อนถอด VAT',
        digits='Product Price',
        help='ราคาเดิมก่อนถอด VAT 7% (ระบบเก็บอัตโนมัติ)',
    )

    exclude_vat = fields.Boolean(
        related='pricelist_id.exclude_vat',
        string='ถอด VAT 7%',
        readonly=True,
    )

    def write(self, vals):
        """เมื่อแก้ไข fixed_price ขณะที่ติ๊กถอด VAT อยู่
        ให้เก็บค่าที่กรอกเป็น price_before_vat แล้วหาร 1.07"""
        if self.env.context.get('skip_vat_calc'):
            return super().write(vals)
        if 'fixed_price' in vals:
            for item in self:
                if item.pricelist_id.exclude_vat:
                    original = vals['fixed_price']
                    if original:
                        vals['price_before_vat'] = original
                        vals['fixed_price'] = round(original / 1.07, 2)
        return super().write(vals)

    @api.model
    def create(self, vals):
        """เมื่อสร้าง item ใหม่ ขณะที่ติ๊กถอด VAT อยู่"""
        if self.env.context.get('skip_vat_calc'):
            return super().create(vals)
        if vals.get('fixed_price') and vals.get('pricelist_id'):
            pricelist = self.env['product.pricelist'].browse(
                vals['pricelist_id']
            )
            if pricelist.exclude_vat:
                original = vals['fixed_price']
                vals['price_before_vat'] = original
                vals['fixed_price'] = round(original / 1.07, 2)
        return super().create(vals)
