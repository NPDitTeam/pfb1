# -*- coding: utf-8 -*-
# import logging
# from odoo import models, fields, api, _
# from odoo.exceptions import UserError
#
# _logger = logging.getLogger(__name__)
#
#
# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     is_rounding_applied = fields.Boolean(
#         string="Rounding Applied",
#         default=False,
#         copy=False,
#     )
#
#     rounding_amount = fields.Float(
#         string="Rounding Amount",
#         default=0.0,
#         copy=False,
#         help="จำนวนเงินที่ปัดเศษ"
#     )
#
#     def action_apply_rounding(self):
#         """
#         ปุ่มอัพเดททศนิยม - ปัดเศษ amount_total ผ่าน SQL
#         """
#         for move in self:
#             if move.state != 'draft':
#                 raise UserError(_('สามารถปัดเศษได้เฉพาะใบแจ้งหนี้ที่เป็นแบบร่างเท่านั้น'))
#
#             if move.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
#                 move._apply_rounding_sql()
#
#         return True
#
#     def _apply_rounding_sql(self):
#         """
#         ปัดเศษ amount_total ผ่าน SQL (ไม่สร้าง line ใหม่)
#         """
#         for move in self:
#             if not move.id:
#                 continue
#
#             # ดึงค่าจาก database โดยตรง
#             self.env.cr.execute("""
#                 SELECT amount_total, amount_residual
#                 FROM account_move
#                 WHERE id = %s
#             """, (move.id,))
#             result = self.env.cr.fetchone()
#
#             if not result:
#                 continue
#
#             db_amount_total, db_amount_residual = result
#
#             # ตรวจสอบว่ามีทศนิยมหรือไม่
#             if not db_amount_total or db_amount_total <= 0:
#                 _logger.warning(f"✅ [ROUNDING] {move.name}: ไม่มียอดให้ปัดเศษ")
#                 continue
#
#             decimal_part = round(float(db_amount_total) % 1, 2)
#
#             # ถ้าเป็นจำนวนเต็มอยู่แล้ว ไม่ต้องปัด
#             if decimal_part == 0:
#                 _logger.warning(f"✅ [ROUNDING] {move.name}: ยอดเป็นจำนวนเต็มแล้ว ({db_amount_total})")
#                 continue
#
#             # คำนวณยอดปัดเศษ (>= 0.50 ปัดขึ้น, < 0.50 ปัดลง)
#             new_amount_total = round(float(db_amount_total))
#             rounding_diff = round(new_amount_total - float(db_amount_total), 2)
#             new_amount_residual = float(db_amount_residual or 0) + rounding_diff
#
#             _logger.warning(f"🔴 [ROUNDING] {move.name}: {db_amount_total} → {new_amount_total} (diff: {rounding_diff})")
#
#             # อัพเดทผ่าน SQL
#             self.env.cr.execute("""
#                 UPDATE account_move
#                 SET amount_total = %s,
#                     amount_residual = %s,
#                     amount_total_signed = %s,
#                     amount_residual_signed = %s,
#                     is_rounding_applied = %s,
#                     rounding_amount = %s
#                 WHERE id = %s
#             """, (
#                 new_amount_total,
#                 new_amount_residual,
#                 new_amount_total,
#                 new_amount_residual,
#                 True,
#                 rounding_diff,
#                 move.id
#             ))
#
#             # Invalidate cache เพื่อให้ ORM รับค่าใหม่
#             move.invalidate_cache()
#
#             _logger.warning(f"✅ [ROUNDING] SQL Updated: {move.name}")
#
#     def button_draft(self):
#         """
#         Override button_draft เพื่อรีเซ็ต rounding flag
#         """
#         res = super(AccountMove, self).button_draft()
#
#         for move in self:
#             self.env.cr.execute("""
#                 UPDATE account_move
#                 SET is_rounding_applied = false,
#                     rounding_amount = 0.0
#                 WHERE id = %s
#             """, (move.id,))
#
#         return res
