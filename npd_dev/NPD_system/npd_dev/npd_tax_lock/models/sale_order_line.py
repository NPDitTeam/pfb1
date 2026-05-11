# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

# ชื่อภาษีที่ต้องการล็อก
TAX_NAME_SALE = 'ภาษีขายไม่รวม Vat 7%'
TAX_NAME_RENT = 'ภาษีขายยังไม่ถึงกำหนด Vat 7%'


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_tax_by_name(self, tax_name):
        """ค้นหาภาษีตามชื่อ"""
        tax = self.env['account.tax'].search([
            ('name', '=', tax_name),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        return tax

    @api.onchange('tax_id')
    def _onchange_tax_id_block(self):
        """ป้องกันการเปลี่ยนภาษีใน UI"""
        # ถ้าผู้ใช้มีสิทธิ์ bypass ให้ข้าม
        if self.env.user.bypass_rental_tax_lock:
            return

        for line in self:
            # ถ้า pfb_so_type = 'sale' ล็อกเป็น ภาษีขายไม่รวม Vat 7%
            if line.order_id.pfb_so_type == 'sale' and line.product_id:
                expected_tax = self._get_tax_by_name(TAX_NAME_SALE)
                if expected_tax and set(line.tax_id.ids) != set([expected_tax.id]):
                    line.tax_id = [(6, 0, [expected_tax.id])]
                    return {
                        'warning': {
                            'title': "ไม่สามารถเปลี่ยนภาษี",
                            'message': "อนุญาตเฉพาะ %s สำหรับใบขายเท่านั้น" % TAX_NAME_SALE,
                            'type': 'warning'
                        }
                    }

            # ถ้า pfb_so_type = 'rent' ล็อกเป็น ภาษีขายยังไม่ถึงกำหนด Vat 7%
            if line.order_id.pfb_so_type == 'rent' and line.product_id:
                expected_tax = self._get_tax_by_name(TAX_NAME_RENT)
                if expected_tax and set(line.tax_id.ids) != set([expected_tax.id]):
                    line.tax_id = [(6, 0, [expected_tax.id])]
                    return {
                        'warning': {
                            'title': "ไม่สามารถเปลี่ยนภาษี",
                            'message': "อนุญาตเฉพาะ %s สำหรับใบเช่าเท่านั้น" % TAX_NAME_RENT,
                            'type': 'warning'
                        }
                    }
