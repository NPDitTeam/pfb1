# -*- coding: utf-8 -*-
# from odoo import models, api
# from odoo.exceptions import UserError
#
#
# class AccountPayment(models.Model):
#     _inherit = 'account.payment'
#
#     def action_draft(self):
#         """ยกเลิกการชำระเงินเป็นร่าง"""
#         if not self.env.user.allow_cancel:
#             raise UserError(
#                 'คุณไม่ได้รับอนุญาตให้ยกเลิกการชำระเงินนี้ '
#                 'กรุณาติดต่อผู้ดูแลระบบ'
#             )
#         return super(AccountPayment, self).action_draft()
#
#     def action_cancel(self):
#         """ยกเลิกการชำระเงิน"""
#         if not self.env.user.allow_cancel:
#             raise UserError(
#                 'คุณไม่ได้รับอนุญาตให้ยกเลิกการชำระเงินนี้ '
#                 'กรุณาติดต่อผู้ดูแลระบบ'
#             )
#         return super(AccountPayment, self).action_cancel()
