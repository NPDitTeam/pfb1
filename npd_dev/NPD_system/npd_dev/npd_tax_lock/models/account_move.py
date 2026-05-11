# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

# ชื่อภาษีที่ต้องการล็อก
TAX_NAME_RENTAL = 'ภาษีขายยังไม่ถึงกำหนด Vat 7%'
TAX_NAME_CREDIT_NOTE = 'ภาษีขายรวม VAT 7%'

# ชื่อสมุดรายวันที่ต้องล็อกภาษี (ภาษีขายยังไม่ถึงกำหนด)
LOCKED_JOURNAL_RENTAL = [
    'สมุดรายวันเช่า(สาขา)',
    'สมุดรายวันค่าปรับหาย',
    'สมุดรายวันค่าปรับชำรุด',
]

# ชื่อสมุดรายวันที่ต้องล็อกภาษี (ภาษีขายรวม)
LOCKED_JOURNAL_CREDIT_NOTE = [
    'สมุดรายวันลดหนี้ขาย',
]

# ชื่อสมุดรายวันที่ไม่ให้ใส่ภาษี
LOCKED_JOURNAL_NO_TAX = [
    'สมุดรายวันค่าประกัน',
]


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_tax_by_name(self, tax_name):
        """ค้นหาภาษีตามชื่อ"""
        tax = self.env['account.tax'].search([
            ('name', '=', tax_name),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        return tax

    @api.onchange('tax_ids')
    def _onchange_tax_ids_block(self):
        """ป้องกันการเปลี่ยนภาษีใน UI"""
        # ถ้าผู้ใช้มีสิทธิ์ bypass ให้ข้าม
        if self.env.user.bypass_rental_tax_lock:
            return

        for line in self:
            if not line.move_id or not line.move_id.journal_id:
                continue

            journal_name = line.move_id.journal_id.name

            # สมุดรายวันค่าประกัน ไม่ให้ใส่ภาษี
            if journal_name in LOCKED_JOURNAL_NO_TAX:
                if line.tax_ids:
                    line.tax_ids = [(5, 0, 0)]
                    return {
                        'warning': {
                            'title': "ไม่สามารถใส่ภาษี",
                            'message': "สมุดรายวัน %s ไม่อนุญาตให้ใส่ภาษี" % journal_name,
                            'type': 'warning'
                        }
                    }

            # สมุดรายวันเช่า ล็อกเป็น ภาษีขายยังไม่ถึงกำหนด Vat 7%
            if journal_name in LOCKED_JOURNAL_RENTAL and line.product_id:
                expected_tax = self._get_tax_by_name(TAX_NAME_RENTAL)
                if expected_tax and set(line.tax_ids.ids) != set([expected_tax.id]):
                    line.tax_ids = [(6, 0, [expected_tax.id])]
                    return {
                        'warning': {
                            'title': "ไม่สามารถเปลี่ยนภาษี",
                            'message': "สมุดรายวัน %s อนุญาตเฉพาะ %s เท่านั้น" % (journal_name, TAX_NAME_RENTAL),
                            'type': 'warning'
                        }
                    }

            # สมุดรายวันลดหนี้ขาย ล็อกเป็น ภาษีขายรวม VAT 7%
            if journal_name in LOCKED_JOURNAL_CREDIT_NOTE and line.product_id:
                expected_tax = self._get_tax_by_name(TAX_NAME_CREDIT_NOTE)
                if expected_tax and set(line.tax_ids.ids) != set([expected_tax.id]):
                    line.tax_ids = [(6, 0, [expected_tax.id])]
                    return {
                        'warning': {
                            'title': "ไม่สามารถเปลี่ยนภาษี",
                            'message': "สมุดรายวัน %s อนุญาตเฉพาะ %s เท่านั้น" % (journal_name, TAX_NAME_CREDIT_NOTE),
                            'type': 'warning'
                        }
                    }
