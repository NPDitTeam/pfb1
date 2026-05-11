from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from docutils.nodes import pending

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def create(self, vals):
        move = super(AccountMove, self).create(vals)

        if move.move_type == 'out_refund' and move.reversed_entry_id:
            original_invoice = move.reversed_entry_id

            if original_invoice.payment_state == 'paid':
                move.partner_id = move.partner_shipping_id

        return move


    def action_post(self):
        for move in self:
            if move.move_type == 'out_refund' and move.reversed_entry_id and move.state == 'draft':
                original_invoice = move.reversed_entry_id

                if original_invoice.payment_state == 'paid' :
                    # 🔍 DEBUG: พิมพ์ชื่อภาษีทั้งหมดในบรรทัดของใบกำกับภาษีต้นทาง

                    # ✅ ตรวจว่ามีบรรทัดใดไม่มี "ภาษีขายรวม VAT 7%" หรือไม่
                    lines_without_vat7 = move.invoice_line_ids.filtered(
                        lambda l: not any(t.name == 'ภาษีขายรวม VAT 7%' for t in l.tax_ids)
                    )

                    if lines_without_vat7:
                        product_name = lines_without_vat7[0].product_id.name if lines_without_vat7[
                            0].product_id else "ไม่พบชื่อสินค้า"
                        raise UserError(_(
                            "⚠️ ไม่สามารถยืนยันใบลดหนี้ได้\n\n"
                            "มีรายการ '%s'\n"
                            "ที่ยังไม่ได้ระบุภาษี 'ภาษีขายรวม VAT 7%%'\n"
                            "กรุณาแก้ไขภาษีให้ครบก่อนดำเนินการ"
                        ) % ( product_name))



                    # for tax_line in move.line_ids.filtered(lambda l: l.tax_line_id):
                    #     tax_line.invalidate_cache()
                    #
                    #     base = tax_line.tax_base_amount or 0.0
                    #     balance = tax_line.balance or 0.0
                    #
                    #     _logger.info(
                    #         f"[DEBUG] ตรวจสอบ Tax Line: base={base}, balance={balance}, credit={tax_line.credit}, debit={tax_line.debit} (line_id={tax_line.id})"
                    #     )
                    #
                    #     if base > 0 or balance > 0:
                    #         raise UserError(_(
                    #             "❌ พบ Tax Line ที่ไม่ได้ติดลบในใบลดหนี้เลขที่: %s\n\n"
                    #             "ค่าที่ถูกต้องควรเป็น:\n"
                    #             "Tax Base = -%.2f\n"
                    #             "Tax Amount = -%.2f\n\n"
                    #             "กรุณาแก้ไขให้เป็นค่าติดลบก่อนโพสต์เอกสาร"
                    #         ) % (move.name, base, balance))


                    # for line in move.line_ids:
                    #     line._update_tax_summary_log()

        # 🔁 ดำเนินการโพสต์ตามปกติ
        return super(AccountMove, self).action_post()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('pfb_quantity', 'pfb_date_of_rent')
    def _onchange_pfb_calculate_quantity(self):
        for line in self:
            move = line.move_id
            if move and move.move_type == 'out_refund' or move.state == 'draft':
                if line.pfb_quantity or line.pfb_date_of_rent:
                    # คำนวณจำนวนใหม่
                    line.quantity = line.pfb_quantity * line.pfb_date_of_rent

                    # ดึงภาษีชื่อ "ภาษีขายรวม VAT 7%"
                    tax = self.env['account.tax'].search([('name', '=', 'ภาษีขายรวม VAT 7%')], limit=1)

                    # ถ้าเจอภาษี ให้กำหนด tax_ids ให้กับบรรทัด
                    if tax:
                        line.tax_ids = [(6, 0, [tax.id])]

                    # 🔁 1. ล้างฟิลด์ tax_ids ออกจากบรรทัด
                    # line.tax_ids = [(5, 0, 0)]





