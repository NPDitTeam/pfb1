# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def button_draft(self):
        """ยกเลิกบันทึกเป็นร่าง"""
        if not self.env.user.allow_cancel:
            raise UserError(
                'คุณไม่ได้รับอนุญาตให้ยกเลิกบันทึกนี้ '
                'กรุณาติดต่อผู้ดูแลระบบ'
            )
        return super(AccountMove, self).button_draft()
#
#     def button_cancel(self):
#         """ยกเลิกบันทึก"""
#         if not self.env.user.allow_cancel:
#             raise UserError(
#                 'คุณไม่ได้รับอนุญาตให้ยกเลิกบันทึกนี้ '
#                 'กรุณาติดต่อผู้ดูแลระบบ'
#             )
#         return super(AccountMove, self).button_cancel()
