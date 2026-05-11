from odoo import models, fields, api, _
from bahttext import bahttext


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # def get_baht_text_disappeared_receipt(self):
    #     amount = self.amount
    #     return bahttext(amount)

    def get_baht_text_disappeared_receipt(self):
        """ดึงยอดหัก ณ ที่จ่ายจากใบแจ้งหนี้"""
        # สำหรับ Odoo 13 ขึ้นไป
        return bahttext(sum(self.reconciled_invoice_ids.mapped('amount_total')))

        # หรือถ้าเป็น Odoo เวอร์ชันเก่า ใช้
        # return sum(self.invoice_ids.mapped('wht_amt_net'))