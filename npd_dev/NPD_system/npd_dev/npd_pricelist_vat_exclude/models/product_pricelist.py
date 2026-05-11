from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    exclude_vat = fields.Boolean(
        string='ถอด VAT 7%',
        default=False,
        help='เมื่อติ๊ก ราคาคงที่ใน Pricelist Items จะถูกคำนวณถอด VAT 7% อัตโนมัติ',
    )

    def write(self, vals):
        # จำสถานะเดิมก่อน
        old_states = {}
        if 'exclude_vat' in vals:
            for pricelist in self:
                old_states[pricelist.id] = pricelist.exclude_vat

        # บันทึกก่อน (รวม item_ids commands ด้วย)
        res = super().write(vals)

        # หลังบันทึกเสร็จ ค่อยคำนวณ VAT
        if 'exclude_vat' in vals:
            new_exclude_vat = vals['exclude_vat']
            for pricelist in self:
                old_exclude_vat = old_states.get(pricelist.id, False)

                # เปลี่ยนจาก ไม่ติ๊ก → ติ๊ก (ถอด VAT)
                if new_exclude_vat and not old_exclude_vat:
                    for item in pricelist.item_ids:
                        if item.fixed_price:
                            original = item.fixed_price
                            new_price = round(original / 1.07, 2)
                            _logger.info(
                                'VAT Exclude: item %s price %s -> %s',
                                item.id, original, new_price
                            )
                            item.with_context(skip_vat_calc=True).write({
                                'price_before_vat': original,
                                'fixed_price': new_price,
                            })

                # เปลี่ยนจาก ติ๊ก → ไม่ติ๊ก (คืน VAT)
                elif not new_exclude_vat and old_exclude_vat:
                    for item in pricelist.item_ids:
                        if item.price_before_vat:
                            _logger.info(
                                'VAT Restore: item %s price %s -> %s',
                                item.id, item.fixed_price,
                                item.price_before_vat
                            )
                            item.with_context(skip_vat_calc=True).write({
                                'fixed_price': item.price_before_vat,
                                'price_before_vat': 0,
                            })

        return res
