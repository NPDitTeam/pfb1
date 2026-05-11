# -*- coding: utf-8 -*-
from odoo import fields, models

class AccountPayment(models.Model):
    _inherit = "account.payment"

    wht_has_slip = fields.Boolean(
        string="ยังไม่ได้รับใบหัก ณ ที่จ่าย",
        default=False,  # ค่าเริ่มต้นไม่ต้องติ๊ก
        help="ติ๊กเมื่อการชำระเงินนี้มีใบหัก ณ ที่จ่ายแนบประกอบ"
    )

    received_payment = fields.Boolean(
        string="ได้รับใบหัก ณ ที่จ่าย",
        store=True,
        default=False,
    )

    pfb_date_of_rent = fields.Float(
        string="Day of Rent",
        store=True,
    )
