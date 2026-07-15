from odoo import api, fields, models
from bahttext import bahttext


class AccountMove(models.Model):
    _inherit = "account.move"

    # ใบแจ้งหนี้ค่าเช่าพื้นที่สำนักงาน (Office space rental invoice)
    # จำนวนเงินทั้งสิ้น = amount_total
    def get_office_rent_total_baht_text(self):
        return bahttext(self.amount_total)

    # เฉพาะบรรทัดรายการสินค้า (ตัด section/note ออก) เพื่อดึงไปแสดงในช่อง "รายการ"
    def get_office_rent_lines(self):
        return self.invoice_line_ids.filtered(
            lambda l: not l.display_type
        )
