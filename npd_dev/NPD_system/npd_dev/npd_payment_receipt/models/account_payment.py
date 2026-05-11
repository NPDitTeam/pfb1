from odoo import models, fields, api, _
from bahttext import bahttext
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    note = fields.Text(string="หมายเหตุ")

    def get_baht_text(self, amount):
        return bahttext(round(amount, 2))

    # r_move_id = fields.Many2one('account.move', string="อ้างอิงใบขาบัญชี(เช่า)" )

    # def get_baht_text_form_receipt(self):
    #     total_untaxed_amount = sum(i.amount_untaxed_signed for i in self.reconciled_invoice_ids)
    #     total_amount = self.total_amount - total_untaxed_amount * 5 / 100
    #     return bahttext(total_amount)
    #
    # def action_rework_reverse_move(self):
    #     for rec in self:
    #         if not rec.invoice_ids:
    #             raise UserError(_("ไม่พบใบแจ้งหนี้ที่แนบกับการชำระเงินนี้"))
    #
    #         payment_invoice = rec.invoice_ids[0]
    #         if not payment_invoice.invoice_id:
    #             raise UserError(_("ไม่พบฟิลด์ invoice_id ที่เชื่อมกับใบแจ้งหนี้"))
    #
    #         old_invoice = payment_invoice.invoice_id
    #
    #         # เช็คว่า invoice_id.name เป็น INV-* หรือไม่
    #         if old_invoice.name.startswith('INV-'):
    #             print("ประเภทใบแจ้งหนี้", old_invoice.name.startswith)
    #             journal = old_invoice.journal_id
    #
    #             _logger.info("📘 ใช้ Journal: %s (ID: %s)", journal.name, journal.id)
    #             _logger.info("🧷 Current Refund Sequence: %s", journal.refund_sequence_id)
    #
    #             # ✅ ตรวจสอบและสร้าง Refund Sequence หากไม่มี
    #             if not journal.refund_sequence_id:
    #                 seq = self.env['ir.sequence'].create({
    #                     'name': 'Refund %s' % journal.name,
    #                     'code': 'refund.%s' % journal.code,
    #                     'prefix': 'RV-INV/%(year)s/',
    #                     'padding': 4,
    #                     'company_id': journal.company_id.id,
    #                 })
    #                 journal.refund_sequence_id = seq.id
    #                 _logger.info("✅ สร้าง Refund Sequence ใหม่: %s", seq.name)
    #
    #             # ✅ ดึงข้อมูลภาษีขายรวม VAT 7% จากตาราง account.tax
    #             tax = self.env['account.tax'].search([('name', '=', 'ภาษีขายรวม VAT 7%')], limit=1)
    #             if not tax:
    #                 raise UserError(_("ไม่พบภาษี 'ภาษีขายรวม VAT 7%' ในระบบ"))
    #
    #             # ✅ เตรียม invoice_line สำหรับ Credit Note
    #             vals = []
    #             for line in old_invoice.invoice_line_ids:
    #                 vals.append((0, 0, {
    #                     'account_id': line.account_id.id,
    #                     'name': line.name,
    #                     'quantity': line.quantity,
    #                     'price_unit': line.price_unit,
    #                     'tax_ids': [(6, 0, [tax.id])],  # ใช้ tax.id ที่ดึงมา
    #                     'product_id': line.product_id.id,
    #                 }))
    #
    #             # ✅ สร้าง Credit Note (ใบลดหนี้)
    #             move = self.env['account.move'].create({
    #                 'move_type': 'out_refund',
    #                 'ref': _("Refund for %s") % old_invoice.name,
    #                 'invoice_origin': old_invoice.name,
    #                 'journal_id': journal.id,
    #                 'partner_id': old_invoice.partner_id.id,
    #                 'invoice_date': rec.date,
    #                 'payment_id': rec.id,
    #                 'invoice_date_due_payment_term': rec.date,
    #                 'invoice_line_ids': vals,
    #                 'company_id': rec.company_id.id,
    #                 'currency_id': old_invoice.currency_id.id,
    #             })
    #
    #             _logger.info("🧾 สร้าง Credit Note: %s", move.name)
    #
    #             # ✅ Post ขาบัญชี
    #             move.action_post()
    #             _logger.info("📌 Credit Note Posted: %s", move.name)
    #
    #             # ✅ บันทึกกลับเข้า payment
    #             rec.r_move_id = move.id
    #             print("rec.r_move_id", rec.r_move_id)
    #             rec.message_post(body=_("สร้างใบลดหนี้: <b>%s</b>") % move.name)

