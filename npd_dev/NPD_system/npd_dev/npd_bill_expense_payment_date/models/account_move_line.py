# -*- coding: utf-8 -*-
from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def reconcile(self):
        """จุด hook เดียวที่ครอบคลุมทุกช่องทางการจ่าย

        ไม่ว่าจะจับคู่ผ่านแถบ outstanding ในบิล ใบสำคัญจ่าย หรือวิซาร์ด
        สุดท้ายลงมาที่เมธอดนี้หมด

        payment_state เป็น stored compute ที่ขึ้นกับ matched_debit_ids
        partial ที่ super() เพิ่งสร้างทำให้ ORM มาร์คไว้ว่าต้องคำนวณใหม่
        แล้วคำนวณให้เองตอนที่เราไปอ่านค่า จึงไม่ต้องสั่ง flush เอง
        """
        results = super(AccountMoveLine, self).reconcile()
        bills = self.mapped("move_id").filtered(
            lambda m: m.move_type == "in_invoice" and m.state == "posted")
        if bills:
            bills._npd_sync_expense_date_to_payment()
        return results
