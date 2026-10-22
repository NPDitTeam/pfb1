# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        # ใบลดหนี้ลูกค้าที่ยืนยันครั้งแรกต้องมี เงื่อนไขและข้อกำหนด (ผู้ใช้สั่ง 22 ต.ค. 2569)
        missing = self.filtered(
            lambda m: m.move_type == 'out_refund' and not m.posted_before
            and not (m.narration or '').strip())
        if missing:
            raise UserError(
                'กรุณากรอก "เงื่อนไขและข้อกำหนด" (หมายเหตุ) ของใบลดหนี้ก่อนยืนยัน\n%s'
                % ', '.join(missing.mapped(lambda m: m.name if m.name and m.name != '/' else 'ใบลดหนี้ร่าง')))
        return super().action_post()
