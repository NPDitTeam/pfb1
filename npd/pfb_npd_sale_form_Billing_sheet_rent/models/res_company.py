# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    bill_payment_biller_id = fields.Char(
        string=u"Comp Code / Biller ID (Bill Payment)",
        help=u"รหัส Comp Code / Biller ID ที่ธนาคารกำหนดสำหรับบริการรับชำระเงิน (Bill Payment) "
             u"ใช้สร้าง QR/บาร์โค้ดบนใบแจ้งหนี้/ใบวางบิล")
