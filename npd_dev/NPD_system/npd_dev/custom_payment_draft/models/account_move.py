import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # @api.model
    # def create(self, vals):
    #     """Override create method เมื่อกดบันทึก"""
    #     record = super().create(vals)
    #     record._get_sale_order_date()
    #     return record
    #
    # def action_post(self):
    #     """Override action_post เมื่อกดยืนยัน"""
    #     for record in self:
    #         record._get_sale_order_date()
    #     return super().action_post()
    #
    # def _get_sale_order_date(self):
    #     """
    #     ค้นหา sale.order จาก invoice_origin
    #     ดึง date_order มาเติมที่วันที่ใบแจ้งหนี้
    #     """
    #     for record in self:
    #         # ข้ามไปถ้าไม่มี invoice_origin หรือ posted แล้ว
    #         if not record.invoice_origin or record.state == 'posted':
    #             continue
    #
    #         # ค้นหา sale.order จากชื่อ order
    #         sale_order = self.env['sale.order'].search(
    #             [('name', '=', record.invoice_origin)],
    #             limit=1
    #         )
    #
    #         if sale_order:
    #             # ดึง date_order จาก sale order
    #             order_date = sale_order.date_order
    #             # ดึง invoice_payment_term_id จาก sale order
    #             payment_term = sale_order.payment_term_id
    #
    #             if order_date:
    #                 # แปลง order_date เป็น date ถ้าเป็น datetime
    #                 if isinstance(order_date, datetime):
    #                     order_date = order_date.date()
    #
    #                 # คำนวณวันครบกำหนดจาก payment term
    #                 invoice_date_due = order_date
    #                 if payment_term:
    #                     try:
    #                         pterm_list = payment_term.compute(
    #                             value=1,
    #                             date_ref=order_date,
    #                             currency=record.currency_id
    #                         )
    #                         # pterm_list เป็น list ของ tuple (date, amount)
    #                         if pterm_list:
    #                             invoice_date_due = max(line[0] for line in pterm_list)
    #                     except Exception as e:
    #                         _logger.error(f"Error computing payment term: {e}")
    #                         invoice_date_due = order_date
    #
    #                 # อัปเดตค่าทั้งหมดพร้อมกัน
    #                 vals_to_write = {
    #                     'invoice_date': order_date,
    #                     'date': order_date,
    #                     'invoice_date_due': invoice_date_due,
    #                 }
    #
    #                 if payment_term:
    #                     vals_to_write['invoice_payment_term_id'] = payment_term.id
    #
    #                 record.write(vals_to_write)
    #
    #                 # อัปเดต invoice lines ให้ตรงกับ invoice date
    #                 if record.invoice_line_ids:
    #                     record.invoice_line_ids.write({'date': order_date})
    #
    #                 _logger.info(
    #                     f"Updated invoice {record.name}: "
    #                     f"date={order_date}, "
    #                     f"payment_term={payment_term.name if payment_term else 'None'}, "
    #                     f"due_date={invoice_date_due} "
    #                     f"from sale order {sale_order.name}"
    #                 )
    #             else:
    #                 _logger.warning(
    #                     f"Sale order {sale_order.name} has no date_order"
    #                 )
    #         else:
    #             _logger.warning(
    #                 f"Sale order not found for invoice_origin: "
    #                 f"{record.invoice_origin}"
    #             )

    def button_draft(self):

        """
        Override button_draft เพื่อยกเลิกการรับชำระเงินก่อนรีเซ็ตเป็นแบบร่าง
        """
        # ยกเลิกการรับชำระเงินที่เกี่ยวข้อง
        for move in self:
            _logger.info(f"📋 button_draft() called for move: {move.name}")
            if move.payment_state == 'paid':
                # หา payments ที่เกี่ยวข้องกับ invoice นี้ และมี payment_method_one_id.name == 'หักเงินประกันค่าเช่า'
                payments = self.env['account.payment'].search([
                    ('search_invoice_name', '=', move.name),
                    # ('state', '!=', 'cancel'),
                    ('payment_method_one_id.name', '=', 'หักเงินประกันค่าเช่า')
                ])

                _logger.info(
                    f"🔍 Found {len(payments)} payment(s) with method 'หักเงินประกันค่าเช่า' for invoice: {move.name}")

                if payments:
                    # ยกเลิก payments
                    for payment in payments:
                        try:
                            _logger.info(f"🔄 Processing payment: {payment.name} | State: {payment.state}")

                            # ถ้า payment ถูก reconcile แล้ว ต้อง unreconcile ก่อน
                            if payment.state == 'posted':
                                _logger.info(f"✅ Payment {payment.name} is posted - attempting to unreconcile")

                                # หา move lines ที่ reconcile
                                move_lines = payment.move_id.line_ids.filtered(
                                    lambda l: l.account_id.reconcile and l.reconciled
                                )

                                if move_lines:
                                    _logger.info(f"🔗 Found {len(move_lines)} reconciled lines")
                                    move_lines.remove_move_reconcile()
                                    _logger.info(f"✅ Unreconciled {len(move_lines)} lines")

                                # ✅ เรียก action_draft ของ account.payment
                                _logger.info(f"📞 Calling payment.action_draft() for {payment.name}")

                                # ต้องเรียกให้ชัดเจนว่าเป็น account.payment
                                AccountPayment = self.env['account.payment']
                                payment_record = AccountPayment.browse(payment.id)

                                # เรียก action_draft ซึ่งจะเรียก logic การยกเลิก sale_order และ picking
                                payment_record.action_draft()

                                _logger.info(f"✅ Payment {payment.name} set to draft state")

                                # ✅ เพิ่ม logic ยกเลิก sale_order และ picking โดยตรง
                                _logger.info(f"🔄 Processing reversal of sale_order and picking...")

                                for invoice_line in payment_record.invoice_ids:
                                    invoice = invoice_line.invoice_id

                                    if invoice and invoice.invoice_origin:
                                        sale_order = self.env['sale.order'].search([
                                            ('name', '=', invoice.invoice_origin)
                                        ], limit=1)

                                        if sale_order:
                                            _logger.info(f"🔍 Found sale_order: {sale_order.name}")

                                            # ยกเลิกการ update sale_order
                                            try:
                                                sale_order.sudo().write({
                                                    'rental_status': 'in_rent',
                                                    'check_state': '',
                                                })
                                                _logger.info(f"✅ Reverted sale_order {sale_order.name} status")
                                            except Exception as e_so:
                                                _logger.warning(f"⚠️ Could not revert sale_order: {str(e_so)}")

                                            # ยกเลิก picking
                                            picking_related = self.env['stock.picking'].search([
                                                ('group_id.name', '=', sale_order.name),
                                                ('name', 'like', '%IN%'),
                                                ('state', '=', 'done')
                                            ], limit=1)

                                            if picking_related:
                                                try:
                                                    picking_related.sudo().write({
                                                        'deposit_return_state': 'not_returned'
                                                    })
                                                    _logger.info(
                                                        f"✅ Reverted picking {picking_related.name} to 'not_returned'")
                                                except Exception as e_pk:
                                                    _logger.warning(f"⚠️ Could not revert picking: {str(e_pk)}")
                                            else:
                                                _logger.warning(f"⚠️ No picking found for {sale_order.name}")

                            elif payment.state == 'draft':
                                _logger.info(f"⚠️ Payment {payment.name} is already in draft state")

                        except Exception as e:
                            _logger.error(f"❌ Error processing payment {payment.name}: {str(e)}", exc_info=True)
                            raise UserError(_(
                                'ไม่สามารถยกเลิกการรับชำระเงิน %s ได้: %s'
                            ) % (payment.name, str(e)))

            # เรียก method เดิมของ Odoo
            _logger.info(f"📋 Calling super().button_draft() for move: {move.name}")
            return super(AccountMove, self).button_draft()

        """
                        Override button_draft เพื่อยกเลิกการรับชำระเงินก่อนรีเซ็ตเป็นแบบร่าง
                        """
        # ยกเลิกการรับชำระเงินที่เกี่ยวข้อง
        for move in self:
            # หา payments ที่เกี่ยวข้องกับ invoice นี้
            payments = self.env['account.payment'].search([
                ('search_invoice_name', '=', move.name),
                # ('state', '!=', 'cancel')
            ])

            if payments:
                # ยกเลิก payments
                for payment in payments:
                    try:
                        # ถ้า payment ถูก reconcile แล้ว ต้อง unreconcile ก่อน
                        if payment.state == 'posted':
                            # หา move lines ที่ reconcile
                            move_lines = payment.move_id.line_ids.filtered(
                                lambda l: l.account_id.reconcile and l.reconciled
                            )
                            if move_lines:
                                move_lines.remove_move_reconcile()

                        # ยกเลิก payment
                        payment.action_cancel()

                    except Exception as e:
                        raise UserError(_(
                            'ไม่สามารถยกเลิกการรับชำระเงิน %s ได้: %s'
                        ) % (payment.name, str(e)))

        # เรียก method เดิมของ Odoo
        # return super(AccountMove, self).button_draft()

# from odoo import models, fields, api, _
# from odoo.exceptions import UserError
#
#
# class accountMoves(models.Model):
#     _inherit = 'account.move'
#
#     def button_draft(self):
#         """
#         Override button_draft เพื่อยกเลิกการรับชำระเงินก่อนรีเซ็ตเป็นแบบร่าง
#         """
#         # ยกเลิกการรับชำระเงินที่เกี่ยวข้อง
#         for move in self:
#             # หา payments ที่เกี่ยวข้องกับ invoice นี้
#             payments = self.env['account.payment'].search([
#                 ('search_invoice_name', '=', move.name),
#                 ('state', '!=', 'cancel')
#             ])
#
#             if payments:
#                 # ยกเลิก payments
#                 for payment in payments:
#                     try:
#                         # ถ้า payment ถูก reconcile แล้ว ต้อง unreconcile ก่อน
#                         if payment.state == 'posted':
#                             # หา move lines ที่ reconcile
#                             move_lines = payment.move_id.line_ids.filtered(
#                                 lambda l: l.account_id.reconcile and l.reconciled
#                             )
#                             if move_lines:
#                                 move_lines.remove_move_reconcile()
#
#                         # ยกเลิก payment
#                         payment.action_cancel()
#
#                     except Exception as e:
#                         raise UserError(_(
#                             'ไม่สามารถยกเลิกการรับชำระเงิน %s ได้: %s'
#                         ) % (payment.name, str(e)))
#
#         # เรียก method เดิมของ Odoo
#         return super(AccountMove, self).button_draft()