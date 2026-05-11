# Copyright 2019 Ecosoft Co., Ltd (https://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    move_name = fields.Char(
        string="Force Number",
        readonly=False,
        default=False,
        copy=False,
        help="""Force invoice number. Use this field if
        you don't want to use the default numbering.""",
    )

    def unlink(self):
        for move in self:
            if move.move_name:
                raise UserError(
                    _(
                        """You cannot delete an invoice after it has been validated"""
                        '''(and received a number). You can set it back to "Draft"'''
                        """state and modify its content, then re-confirm it."""
                    )
                )
        return super(AccountMove, self).unlink()

    def action_post(self):
        for move in self:
            if move.move_name:
                move.write({"name": move.move_name})
        return super(AccountMove, self).action_post()
    # def action_post(self):
    #
    #     for move in self:
    #         if move.move_name:
    #             move.write({"name": move.move_name})
    #
    #             # ✅ เช็คเฉพาะ Invoice ที่มีการอ้างอิงกับ SO
    #         if not move.invoice_origin:
    #             continue
    #
    #         mismatch_lines = []
    #
    #         # 🔍 หา Sale Order จาก invoice_origin
    #         sale_order = self.env['sale.order'].search([
    #             ('name', '=', move.invoice_origin)
    #         ], limit=1)
    #
    #         if not sale_order:
    #             continue  # ข้ามถ้าไม่พบใบเสนอราคา
    #
    #         for sale_line in sale_order.order_line:
    #             product = sale_line.product_id
    #             so_qty = sale_line.product_uom_qty
    #
    #             # 🔍 รวมยอด invoice สำหรับสินค้านี้ที่เชื่อมกับ sale_line นี้
    #             matched_invoice_lines = move.invoice_line_ids.filtered(
    #                 lambda l: product == l.product_id and sale_line in l.sale_line_ids
    #             )
    #
    #             if matched_invoice_lines:
    #                 invoice_qty = sum(matched_invoice_lines.mapped('quantity'))
    #             else:
    #                 invoice_qty = 0.0
    #
    #             if round(invoice_qty, 2) != round(so_qty, 2):
    #                 if invoice_qty == 0.0:
    #                     reason = "❌ ยังไม่ถูกสร้างในใบแจ้งหนี้"
    #                 else:
    #                     reason = f"⚠️ จำนวนไม่ครบ (SO: {so_qty}, Invoice: {invoice_qty})"
    #
    #                 mismatch_lines.append(f"- {product.display_name}: {reason}")
    #
    #         if mismatch_lines:
    #             msg = "\n".join(mismatch_lines)
    #             raise UserError(
    #                 _("❗ พบสินค้าที่ยังไม่ถูกวางบิลครบจากใบเสนอราคา %s:\n\n%s") % (move.invoice_origin, msg))
    #
    #     return super(AccountMove, self).action_post()