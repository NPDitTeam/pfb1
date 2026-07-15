from odoo import models, fields, api, _
from bahttext import bahttext
from odoo.tools import format_date
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'stock.picking'

    # def get_baht_text(self):
    #     calc = sum(self.order_line.mapped('pfb_amount'))
    #     sum_amount = self.amount_total + self.pfb_amount
    #     return bahttext(sum_amount)

    def get_baht_text_inventory_overview_rental_return_form(self):
        total_amount = 00.00
        return bahttext(total_amount)

    def _get_formatted_commitment_date(self):
        if self.sale_id and self.sale_id.commitment_date:
            return format_date(self.env, self.sale_id.commitment_date, date_format='dd/MM/yyyy')
        return ""

    def _get_formatted_order_date(self):
        """วันที่สั่งซื้อ (date_order) รูปแบบ dd/MM/yyyy -- ใช้แสดง 'กำหนดชำระค่าขนส่งวันที่'"""
        if self.sale_id and self.sale_id.date_order:
            return format_date(self.env, self.sale_id.date_order, date_format='dd/MM/yyyy')
        return ""

    def _get_rental_contract_display(self):
        """เลขที่สัญญาเช่าจากฟิลด์ rental_contract_ref (ดึงมาเก็บผ่านปุ่มดึงข้อมูลการเช่า)
        เช็ค _fields ก่อน กัน DB ที่ไม่ได้ติดตั้ง sale_api_rent -> ไม่ให้ report error"""
        so = self.sale_id
        if so and 'rental_contract_ref' in so._fields:
            return so.rental_contract_ref or ""
        return ""

    def _get_report_values(self, docids, data=None):
        docs = self.env["stock.picking"].browse(docids)
        for doc in docs:
            _logger.info("move_ids_without_package: %s", doc.move_ids_without_package)
        return {
            "docs": docs,
        }