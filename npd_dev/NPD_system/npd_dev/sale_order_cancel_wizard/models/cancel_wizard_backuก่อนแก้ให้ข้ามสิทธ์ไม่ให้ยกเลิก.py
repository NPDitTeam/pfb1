from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import datetime, date
import pytz

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cancel_summary = fields.Text(string="สรุปรายการยกเลิก")

    def copy(self, default=None):
        default = dict(default or {})
        default['cancel_summary'] = ""  # ✅ ล้างค่ายกเลิกตอน duplicate
        return super(SaleOrder, self).copy(default)

    def action_open_cancel_wizard(self):
        """เช็คสิทธิ์ก่อนเปิด Wizard"""
        # ถ้าไม่ติ๊ก cancel_rent_same_day (ยกเลิกได้เฉพาะวันที่สั่งเช่า)
        if not self.env.user.cancel_rent_same_day:
            if self.date_order:
                order_date = self.date_order.date() if isinstance(self.date_order, datetime) else self.date_order
                today = date.today()
                if order_date != today:
                    # แจ้งเตือนทันที
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('ไม่สามารถยกเลิกได้'),
                            'message': _('คุณสามารถยกเลิกได้เฉพาะในวันที่สั่งเช่าเท่านั้น'),
                            'type': 'danger',
                        }
                    }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('ไม่สามารถยกเลิกได้'),
                        'message': _('ไม่พบวันที่สั่งเช่า'),
                        'type': 'danger',
                    }
                }

        # ถ้าผ่านการตรวจสอบ ให้เปิด Wizard
        return {
            'name': 'ยกเลิกรายการอ้างอิงบิลเช่า',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_id': self.id},
        }


class SaleOrderCancelWizard(models.TransientModel):
    _name = 'sale.order.cancel.wizard'
    _description = 'Cancel Related Documents Wizard'

    sale_id = fields.Many2one('sale.order', required=True)
    cancel_sale_order = fields.Boolean("ยกเลิกใบเช่า")
    cancel_invoice = fields.Boolean("ยกเลิกใบแจ้งหนี้")
    cancel_delivery = fields.Boolean("ยกเลิกใบจัดส่งสินค้า")
    cancel_stock_cut = fields.Boolean("ยกเลิกการตัดสต๊อกสินค้า")
    cancel_insurance = fields.Boolean("ยกเลิกใบแจ้งหนี้รับเงินประกัน")
    cancel_payment = fields.Boolean("ยกเลิกใบรับชำระเงิน")
    cancel_debit_note = fields.Boolean("ยกเลิก Debit Note")
    select_all = fields.Boolean("เลือกทั้งหมด")
    cancel_summary = fields.Text(
        string="สรุปรายการยกเลิก",
        related='sale_id.cancel_summary',
        readonly=True,
    )

    @api.model
    def default_get(self, fields):
        res = super(SaleOrderCancelWizard, self).default_get(fields)
        if 'default_sale_id' in self.env.context:
            sale = self.env['sale.order'].browse(self.env.context['default_sale_id'])
            res['cancel_summary'] = sale.cancel_summary
        return res

    @api.onchange('select_all')
    def _onchange_select_all(self):
        """เมื่อติ๊ก/ยกเลิกติ๊ก เลือกทั้งหมด ให้ติ๊ก/ยกเลิกติ๊กรายการทั้งหมด"""
        if self.select_all:
            self.cancel_sale_order = True
            self.cancel_invoice = True
            self.cancel_delivery = True
            self.cancel_stock_cut = True
            self.cancel_insurance = True
            self.cancel_payment = True
            self.cancel_debit_note = True
        else:
            self.cancel_sale_order = False
            self.cancel_invoice = False
            self.cancel_delivery = False
            self.cancel_stock_cut = False
            self.cancel_insurance = False
            self.cancel_payment = False
            self.cancel_debit_note = False

    @api.onchange('cancel_sale_order')
    def _onchange_cancel_sale_order(self):
        """ถ้าติ๊กยกเลิกใบเช่า (ต้นทาง) → บังคับติ๊กอื่นทั้งหมดด้วย"""
        if self.cancel_sale_order:
            self.cancel_invoice = True
            self.cancel_delivery = True
            self.cancel_stock_cut = True
            self.cancel_insurance = True
            self.cancel_payment = True
            self.cancel_debit_note = True

    @api.onchange('cancel_invoice', 'cancel_delivery', 'cancel_stock_cut', 'cancel_insurance',
                  'cancel_payment', 'cancel_debit_note')
    def _onchange_cancel_options(self):
        """ตรวจสอบ select_all"""
        all_selected = (self.cancel_sale_order and self.cancel_invoice and
                        self.cancel_delivery and self.cancel_stock_cut and
                        self.cancel_insurance and self.cancel_payment and
                        self.cancel_debit_note)

        none_selected = (not self.cancel_sale_order and not self.cancel_invoice and
                         not self.cancel_delivery and not self.cancel_stock_cut and
                         not self.cancel_insurance and not self.cancel_payment and
                         not self.cancel_debit_note)

        if all_selected:
            self.select_all = True
        elif none_selected:
            self.select_all = False
        else:
            self.select_all = False

    def _is_return_picking(self, picking):
        """เช็คว่า picking นี้เป็น return picking หรือไม่"""
        # ถ้า move_lines มี origin_returned_move_id แสดงว่าเป็น return picking
        return any(m.origin_returned_move_id for m in picking.move_lines)

    def _has_been_returned(self, picking):
        """เช็คว่า picking นี้ถูก return (คืนสต๊อก) ไปแล้วหรือยัง"""
        for move in picking.move_lines.filtered(lambda m: m.state == 'done'):
            # ถ้ามี returned_move_ids ที่ state = done แสดงว่าถูก return แล้ว
            returned_done = move.returned_move_ids.filtered(lambda rm: rm.state == 'done')
            if returned_done:
                return True
        return False

    def _handle_stock_return(self, picking, tz):
        """จัดการการคืนสต๊อกสำหรับ picking ที่ done แล้ว"""
        messages = []
        now_thai = datetime.now(tz)

        if picking.state == 'done':
            picking_type = picking.picking_type_id.code if picking.picking_type_id else 'N/A'
            has_returned = self._has_been_returned(picking)
            _logger.info("🔵 [STOCK_V4] Checking picking %s: picking_type=%s, has_been_returned=%s",
                         picking.name, picking_type, has_returned)

            # ข้าม incoming (รับสต๊อกเข้า / คืนสต๊อก) - ไม่ต้อง reverse
            if picking_type == 'incoming':
                messages.append(
                    "ℹ️ ข้าม %s (เป็นใบรับสินค้าเข้า ไม่ต้องคืนซ้ำ) (%s)" %
                    (picking.name, now_thai.strftime('%d/%m/%Y %H:%M:%S'))
                )
                return messages

            # ถ้าเป็น outgoing (ตัดสต๊อกออก) → เช็คว่าถูก return ไปแล้วหรือยัง
            if has_returned:
                messages.append(
                    "ℹ️ ข้าม %s (คืนสต๊อกไปแล้วก่อนหน้านี้) (%s)" %
                    (picking.name, now_thai.strftime('%d/%m/%Y %H:%M:%S'))
                )
                return messages

            # outgoing + ยังไม่คืน → สร้าง return เพื่อเอาสต๊อกกลับ
            done_moves = picking.move_lines.filtered(lambda m: m.state == 'done' and m.quantity_done > 0)
            if done_moves:
                try:
                    # สร้าง return picking
                    return_wiz = self.env['stock.return.picking'].with_context(active_id=picking.id).create({
                        'picking_id': picking.id,
                        'location_id': picking.location_id.id,
                        'product_return_moves': [(0, 0, {
                            'product_id': move.product_id.id,
                            'quantity': move.quantity_done,
                            'move_id': move.id,
                        }) for move in done_moves],
                    })

                    # สร้าง return และ validate
                    return_action = return_wiz.create_returns()
                    return_pick_id = return_action.get('res_id')

                    if return_pick_id:
                        return_pick = self.env['stock.picking'].browse(return_pick_id)
                        _logger.info("🔵 [STOCK_V5] Return picking created: %s (state=%s)", return_pick.name, return_pick.state)

                        return_pick.action_confirm()
                        return_pick.action_assign()

                        # ✅ ตั้งค่า quantity_done บน move lines ก่อน validate
                        # Odoo 14: ถ้าไม่ตั้ง quantity_done จะ return wizard stock.immediate.transfer แทน
                        for move_line in return_pick.move_lines:
                            move_line.quantity_done = move_line.product_uom_qty
                            _logger.info("🔵 [STOCK_V5] Set quantity_done=%s for product %s on move %s",
                                         move_line.quantity_done, move_line.product_id.name, move_line.id)

                        # ตั้งค่า move_line_ids (detailed operations) ด้วยถ้ามี
                        for sml in return_pick.move_line_ids:
                            if sml.qty_done == 0:
                                sml.qty_done = sml.product_uom_qty
                                _logger.info("🔵 [STOCK_V5] Set move_line_ids qty_done=%s for %s",
                                             sml.qty_done, sml.product_id.name)

                        # validate - ตอนนี้ quantity_done ถูกตั้งแล้ว ควรผ่านไป done โดยตรง
                        validate_result = return_pick.sudo().button_validate()
                        _logger.info("🔵 [STOCK_V5] button_validate() result: %s", validate_result)

                        # ถ้า button_validate return wizard (เช่น stock.immediate.transfer)
                        if isinstance(validate_result, dict) and validate_result.get('res_model'):
                            wizard_model = validate_result.get('res_model')
                            _logger.info("🔵 [STOCK_V5] Got wizard: %s, processing...", wizard_model)
                            if wizard_model == 'stock.immediate.transfer':
                                immediate_wiz = self.env['stock.immediate.transfer'].create({
                                    'pick_ids': [(6, 0, [return_pick.id])],
                                })
                                immediate_wiz.process()
                                _logger.info("🔵 [STOCK_V5] stock.immediate.transfer processed")
                            elif wizard_model == 'stock.backorder.confirmation':
                                backorder_wiz = self.env['stock.backorder.confirmation'].create({
                                    'pick_ids': [(6, 0, [return_pick.id])],
                                })
                                backorder_wiz.process()
                                _logger.info("🔵 [STOCK_V5] stock.backorder.confirmation processed")

                        # ตรวจสอบสถานะสุดท้าย
                        return_pick.invalidate_cache()
                        _logger.info("🔵 [STOCK_V5] Final state of return picking %s: %s", return_pick.name, return_pick.state)

                        if return_pick.state == 'done':
                            messages.append(
                                "🔁 คืนสต๊อก %s เรียบร้อย (สถานะ: เสร็จสิ้น, คืน %d รายการ) (%s)" %
                                (picking.name, len(done_moves), now_thai.strftime('%d/%m/%Y %H:%M:%S'))
                            )
                        else:
                            messages.append(
                                "⚠️ คืนสต๊อก %s สร้างใบคืนแล้ว (%s) แต่สถานะ: %s (ยังไม่เสร็จสิ้น) (%s)" %
                                (picking.name, return_pick.name, return_pick.state, now_thai.strftime('%d/%m/%Y %H:%M:%S'))
                            )
                except Exception as e:
                    _logger.error("🔴 [STOCK_V5] Error returning stock for picking %s: %s", picking.name, str(e))
                    messages.append(
                        "⚠️ ไม่สามารถคืนสต๊อก %s: %s" % (picking.name, str(e))
                    )
        elif picking.state not in ['cancel']:
            picking.action_cancel()
            messages.append(
                "📦 ยกเลิก %s ที่รอดำเนินการ (%s)" %
                (picking.name, now_thai.strftime('%d/%m/%Y %H:%M:%S'))
            )

        return messages

    def confirm_cancel(self):
        """ยกเลิกเอกสารที่เกี่ยวข้องกับการจัดการ Transaction อย่างถูกต้อง"""
        # ตรวจสอบว่าเลือกรายการอะไรบ้าง
        selected_items = []
        if self.cancel_sale_order:
            selected_items.append("ใบเช่า")
        if self.cancel_invoice:
            selected_items.append("ใบแจ้งหนี้")
        if self.cancel_delivery:
            selected_items.append("ใบจัดส่งสินค้า")
        if self.cancel_stock_cut:
            selected_items.append("การตัดสต๊อกสินค้า")
        if self.cancel_insurance:
            selected_items.append("ใบแจ้งหนี้รับเงินประกัน")
        if self.cancel_payment:
            selected_items.append("ใบรับชำระเงิน")
        if self.cancel_debit_note:
            selected_items.append("Debit Note")

        # ถ้าไม่ได้เลือกอะไรเลย
        if not selected_items:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('กรุณาเลือกรายการ'),
                    'message': _('กรุณาเลือกรายการที่ต้องการยกเลิกอย่างน้อย 1 รายการ'),
                    'type': 'warning',
                }
            }

        # ใช้ savepoint เพื่อจัดการ transaction
        messages = []
        tz = pytz.timezone('Asia/Bangkok')

        # ✅ เก็บชื่อ invoice ไว้ก่อน (ก่อนที่จะ cancel invoice)
        # ใช้สำหรับค้นหา payment ทีหลังผ่าน search_invoice_name
        # รวมทั้ง invoice_ids, rent_check, และ debit note (ค้นจาก invoice_origin = SO)
        invoice_names = [inv.name for inv in self.sale_id.invoice_ids if inv.name]
        if hasattr(self.sale_id, 'rent_check'):
            for inv in self.sale_id.rent_check:
                if inv.name and inv.name not in invoice_names:
                    invoice_names.append(inv.name)
        # รวม account.move ทั้งหมดที่มี invoice_origin = เลข SO (จับ debit note ที่ไม่อยู่ใน invoice_ids ด้วย)
        so_name = self.sale_id.name
        all_moves_by_so = self.env['account.move'].sudo().search([
            ('invoice_origin', '=', so_name),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('id', 'not in', self.sale_id.invoice_ids.ids),  # เฉพาะตัวที่ไม่อยู่ใน invoice_ids
        ])
        for mv in all_moves_by_so:
            if mv.name and mv.name not in invoice_names:
                invoice_names.append(mv.name)
        _logger.info("🔵 [CANCEL_WIZARD_V4] All invoice_names (invoices + rent_check + extra moves via SO) = %s", invoice_names)
        _logger.info("🔵 [CANCEL_WIZARD_V4] Extra moves found via invoice_origin='%s' (not in invoice_ids): %s",
                     so_name, [mv.name for mv in all_moves_by_so])

        try:
            # สร้าง savepoint
            self.env.cr.execute("SAVEPOINT cancel_operation")

            # 🔴 ยกเลิกใบเช่า พร้อมจัดการสต๊อกอัตโนมัติ
            if self.cancel_sale_order:
                now_thai = datetime.now(tz)

                # จัดการสต๊อกก่อนยกเลิกใบเช่า
                stock_messages = []
                for picking in self.sale_id.picking_ids:
                    stock_msg = self._handle_stock_return(picking, tz)
                    stock_messages.extend(stock_msg)

                # ยกเลิกใบเช่า
                if self.sale_id.state not in ['cancel', 'done']:
                    try:
                        # ใช้ sudo() เพื่อข้ามการตรวจสอบสิทธิ์ที่อาจติดขัด
                        self.sale_id.sudo().action_cancel()

                        # ตรวจสอบสถานะหลังยกเลิก
                        if self.sale_id.state != 'cancel':
                            # Force update state
                            self.env.cr.execute("""
                                UPDATE sale_order 
                                SET state = 'cancel' 
                                WHERE id = %s
                            """, (self.sale_id.id,))

                        messages.append("📄 ยกเลิกใบเช่า %s เรียบร้อย (สถานะ: %s) (%s)" %
                                        (self.sale_id.name, 'cancel', now_thai.strftime('%d/%m/%Y %H:%M:%S')))

                        # เพิ่มข้อความเกี่ยวกับสต๊อกถ้ามี
                        if stock_messages:
                            messages.append("  └─ การจัดการสต๊อก:")
                            for msg in stock_messages:
                                messages.append("     " + msg)

                    except Exception as e:
                        _logger.error("Error cancelling sale order %s: %s", self.sale_id.name, str(e))
                        messages.append("⚠️ ไม่สามารถยกเลิกใบเช่า %s: %s" % (self.sale_id.name, str(e)))

                elif self.sale_id.state == 'done':
                    messages.append("ℹ️ ใบเช่า %s อยู่ในสถานะ done ไม่สามารถยกเลิกได้ (%s)" %
                                    (self.sale_id.name, now_thai.strftime('%d/%m/%Y %H:%M:%S')))
                else:
                    messages.append("ℹ️ ใบเช่ายกเลิกไปแล้วก่อนหน้านี้ (%s)" % now_thai.strftime('%d/%m/%Y %H:%M:%S'))

            # ยกเลิกใบแจ้งหนี้
            if self.cancel_invoice:
                now_thai = datetime.now(tz)
                cancelled_invoices = []
                for invoice in self.sale_id.invoice_ids:
                    if invoice.state != 'cancel':
                        try:
                            self.env.cr.execute("SAVEPOINT cancel_invoice_op")
                            if invoice.state == 'posted':
                                invoice.sudo().button_draft()
                            invoice.sudo().button_cancel()
                            self.env.cr.execute("RELEASE SAVEPOINT cancel_invoice_op")
                            cancelled_invoices.append(invoice.name or str(invoice.id))
                        except Exception as e:
                            self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_invoice_op")
                            _logger.error("Error cancelling invoice %s: %s", invoice.name, str(e))
                            messages.append(
                                "⚠️ ไม่สามารถยกเลิกใบแจ้งหนี้ %s: %s" % (invoice.name or str(invoice.id), str(e)))

                if cancelled_invoices:
                    messages.append("✅ ยกเลิกใบแจ้งหนี้ %d ใบ (%s)" %
                                    (len(cancelled_invoices), now_thai.strftime('%d/%m/%Y %H:%M:%S')))
                    for inv_name in cancelled_invoices:
                        messages.append("  └─ %s" % inv_name)

            # ยกเลิกใบจัดส่งสินค้า (แยกจากการยกเลิกใบเช่า)
            if self.cancel_delivery and not self.cancel_sale_order:
                now_thai = datetime.now(tz)
                for picking in self.sale_id.picking_ids:
                    if picking.state not in ['cancel', 'done']:
                        try:
                            self.env.cr.execute("SAVEPOINT cancel_delivery_op")
                            picking.sudo().action_cancel()
                            self.env.cr.execute("RELEASE SAVEPOINT cancel_delivery_op")
                            messages.append("📦 ยกเลิก %s เรียบร้อย (%s)" %
                                            (picking.name, now_thai.strftime('%d/%m/%Y %H:%M:%S')))
                        except Exception as e:
                            self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_delivery_op")
                            _logger.error("Error cancelling delivery %s: %s", picking.name, str(e))
                            messages.append("⚠️ ไม่สามารถยกเลิกใบจัดส่ง %s: %s" % (picking.name, str(e)))

            # ยกเลิกการตัดสต๊อก (แยกจากการยกเลิกใบเช่า)
            if self.cancel_stock_cut and not self.cancel_sale_order:
                now_thai = datetime.now(tz)
                done_pickings = self.sale_id.picking_ids.filtered(lambda p: p.state == 'done')
                if done_pickings:
                    for picking in done_pickings:
                        stock_msg = self._handle_stock_return(picking, tz)
                        messages.extend(stock_msg)
                else:
                    messages.append(
                        "ℹ️ ไม่พบรายการตัดสต็อกที่ต้องคืน (ยังไม่มีการตัดสต็อก) (%s)" %
                        now_thai.strftime('%d/%m/%Y %H:%M:%S')
                    )

            # ยกเลิกใบรับเงินประกัน
            if self.cancel_insurance:
                now_thai = datetime.now(tz)
                cancelled_insurance = []
                if hasattr(self.sale_id, 'rent_check'):
                    for inv in self.sale_id.rent_check:
                        if inv.state != 'cancel':
                            try:
                                self.env.cr.execute("SAVEPOINT cancel_insurance_op")
                                if inv.state == 'posted':
                                    inv.sudo().button_draft()
                                inv.sudo().button_cancel()
                                self.env.cr.execute("RELEASE SAVEPOINT cancel_insurance_op")
                                cancelled_insurance.append(inv.name or str(inv.id))
                            except Exception as e:
                                self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_insurance_op")
                                _logger.error("Error cancelling insurance %s: %s", inv.name, str(e))
                                messages.append(
                                    "⚠️ ไม่สามารถยกเลิกใบรับเงินประกัน %s: %s" % (inv.name or str(inv.id), str(e)))

                    if cancelled_insurance:
                        messages.append("🧾 ยกเลิกใบรับเงินประกัน %d ใบ (%s)" %
                                        (len(cancelled_insurance), now_thai.strftime('%d/%m/%Y %H:%M:%S')))

            # ยกเลิกใบรับชำระเงิน (เปลี่ยนเป็นฉบับร่าง)
            if self.cancel_payment:
                now_thai = datetime.now(tz)
                _logger.info("🔵 [CANCEL_PAYMENT_V3] Starting cancel_payment logic")
                _logger.info("🔵 [CANCEL_PAYMENT_V3] invoice_names = %s", invoice_names)

                AccountPayment = self.env['account.payment'].sudo()
                found_payments = AccountPayment

                # === วิธีที่ 1: ค้นจาก search_invoice_name ===
                for inv_name in invoice_names:
                    pays = AccountPayment.search([
                        ('search_invoice_name', 'ilike', inv_name),
                        ('state', '!=', 'cancel'),
                    ])
                    _logger.info("🔵 [CANCEL_PAYMENT_V3] search_invoice_name ilike '%s' => found %d payment(s): %s",
                                 inv_name, len(pays), [p.name for p in pays])
                    found_payments |= pays

                # === วิธีที่ 2: ค้นจาก account.payment.invoice model โดยตรง ===
                all_invoices = self.sale_id.invoice_ids
                if hasattr(self.sale_id, 'rent_check'):
                    all_invoices |= self.sale_id.rent_check
                if all_invoices:
                    PaymentInvoice = self.env['account.payment.invoice'].sudo()
                    pay_inv_lines = PaymentInvoice.search([
                        ('invoice_id', 'in', all_invoices.ids),
                    ])
                    for pi in pay_inv_lines:
                        if pi.payment_id and pi.payment_id.state != 'cancel':
                            found_payments |= pi.payment_id
                    _logger.info("🔵 [CANCEL_PAYMENT_V3] account.payment.invoice search => found %d line(s), payments: %s",
                                 len(pay_inv_lines), [pi.payment_id.name for pi in pay_inv_lines if pi.payment_id])

                _logger.info("🔵 [CANCEL_PAYMENT_V3] Total unique found_payments = %d: %s",
                             len(found_payments), [p.name for p in found_payments])

                cancelled_payments = []
                for pay in found_payments:
                    try:
                        self.env.cr.execute("SAVEPOINT cancel_payment_op")
                        payment_move = pay.move_id
                        _logger.info("🔵 [CANCEL_PAYMENT_V3] Processing payment %s (state=%s), move_id=%s (move_state=%s)",
                                     pay.name, pay.state, payment_move.name, payment_move.state)

                        if pay.state == 'posted':
                            # ---- Unreconcile + Draft โดยตรง (bypass custom override) ----
                            # 1) Unreconcile ทุก reconciled lines ของ payment move
                            reconciled_lines = payment_move.line_ids.filtered(
                                lambda l: l.account_id.reconcile and l.reconciled
                            )
                            if reconciled_lines:
                                reconciled_lines.remove_move_reconcile()
                                _logger.info("🔵 [CANCEL_PAYMENT_V3] Unreconciled %d lines", len(reconciled_lines))

                            # 2) ลบ analytic lines
                            payment_move.mapped('line_ids.analytic_line_ids').unlink()

                            # 3) Set draft โดยตรงผ่าน write (bypass custom button_draft)
                            payment_move.write({'state': 'draft', 'is_move_sent': False})
                            _logger.info("🔵 [CANCEL_PAYMENT_V3] Set move to DRAFT via direct write()")

                        # 4) Draft → Cancel
                        payment_move.write({'auto_post': False, 'state': 'cancel'})
                        _logger.info("🔵 [CANCEL_PAYMENT_V3] Set move to CANCEL via direct write() => DONE for %s", pay.name)

                        self.env.cr.execute("RELEASE SAVEPOINT cancel_payment_op")
                        cancelled_payments.append(pay.name or str(pay.id))
                    except Exception as e:
                        try:
                            self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_payment_op")
                        except Exception:
                            pass
                        _logger.error("🔴 [CANCEL_PAYMENT_V3] Error cancelling payment %s: %s", pay.name, str(e))
                        messages.append(
                            "⚠️ ไม่สามารถยกเลิกใบรับชำระเงิน %s: %s" % (pay.name or str(pay.id), str(e)))

                if cancelled_payments:
                    messages.append("💰 ยกเลิกใบรับชำระเงิน %d ใบ (%s)" %
                                    (len(cancelled_payments), now_thai.strftime('%d/%m/%Y %H:%M:%S')))
                elif invoice_names and not found_payments:
                    messages.append("ℹ️ ไม่พบใบรับชำระเงินที่เกี่ยวข้องกับ invoice: %s" % ', '.join(invoice_names))

            # ยกเลิก Debit Note (ค้นจาก invoice_origin = เลข SO, ไม่อยู่ใน invoice_ids ปกติ)
            if self.cancel_debit_note:
                now_thai = datetime.now(tz)
                cancelled_debit_notes = []

                # ค้นหา debit note: account.move ที่มี invoice_origin = SO แต่ไม่อยู่ใน invoice_ids
                so_name = self.sale_id.name
                existing_inv_ids = self.sale_id.invoice_ids.ids
                all_debit_notes = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so_name),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('id', 'not in', existing_inv_ids),
                    ('state', '!=', 'cancel'),
                ])
                _logger.info("🔵 [DEBIT_NOTE_V4] Search debit notes: invoice_origin='%s', not in invoice_ids=%s => found %d: %s",
                             so_name, existing_inv_ids, len(all_debit_notes), [dn.name for dn in all_debit_notes])

                for dn in all_debit_notes:
                    try:
                        self.env.cr.execute("SAVEPOINT cancel_debit_note_op")
                        _logger.info("🔵 [DEBIT_NOTE_V4] Processing debit note %s (state=%s, reversed_entry=%s)",
                                     dn.name, dn.state, dn.reversed_entry_id.name if dn.reversed_entry_id else 'N/A')

                        if dn.state == 'posted':
                            # Bypass custom button_draft - ใช้ direct write เหมือน payment
                            reconciled_lines = dn.line_ids.filtered(
                                lambda l: l.account_id.reconcile and l.reconciled
                            )
                            if reconciled_lines:
                                reconciled_lines.remove_move_reconcile()
                            dn.mapped('line_ids.analytic_line_ids').unlink()
                            dn.write({'state': 'draft', 'is_move_sent': False})

                        dn.write({'auto_post': False, 'state': 'cancel'})
                        self.env.cr.execute("RELEASE SAVEPOINT cancel_debit_note_op")
                        cancelled_debit_notes.append(dn.name or str(dn.id))
                        _logger.info("🔵 [DEBIT_NOTE_V4] Cancelled debit note %s => DONE", dn.name)
                    except Exception as e:
                        try:
                            self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_debit_note_op")
                        except Exception:
                            pass
                        _logger.error("🔴 [DEBIT_NOTE_V4] Error cancelling debit note %s: %s", dn.name, str(e))
                        messages.append(
                            "⚠️ ไม่สามารถยกเลิก Debit Note %s: %s" % (dn.name or str(dn.id), str(e)))

                if cancelled_debit_notes:
                    messages.append("📝 ยกเลิก Debit Note %d ใบ (%s)" %
                                    (len(cancelled_debit_notes), now_thai.strftime('%d/%m/%Y %H:%M:%S')))
                    for dn_name in cancelled_debit_notes:
                        messages.append("  └─ %s" % dn_name)

                # ยกเลิก payment ที่เกี่ยวกับ debit note ด้วย
                dn_names = [dn.name for dn in all_debit_notes if dn.name]
                if dn_names:
                    AccountPayment = self.env['account.payment'].sudo()
                    dn_payments = AccountPayment
                    for dn_name in dn_names:
                        pays = AccountPayment.search([
                            ('search_invoice_name', 'ilike', dn_name),
                            ('state', '!=', 'cancel'),
                        ])
                        dn_payments |= pays
                    # ค้นจาก account.payment.invoice ด้วย
                    PaymentInvoice = self.env['account.payment.invoice'].sudo()
                    pi_lines = PaymentInvoice.search([('invoice_id', 'in', all_debit_notes.ids)])
                    for pi in pi_lines:
                        if pi.payment_id and pi.payment_id.state != 'cancel':
                            dn_payments |= pi.payment_id

                    _logger.info("🔵 [DEBIT_NOTE_V4] Payments linked to debit notes: %d: %s",
                                 len(dn_payments), [p.name for p in dn_payments])

                    cancelled_dn_payments = []
                    for pay in dn_payments:
                        try:
                            self.env.cr.execute("SAVEPOINT cancel_dn_payment_op")
                            payment_move = pay.move_id
                            if pay.state == 'posted':
                                reconciled_lines = payment_move.line_ids.filtered(
                                    lambda l: l.account_id.reconcile and l.reconciled
                                )
                                if reconciled_lines:
                                    reconciled_lines.remove_move_reconcile()
                                payment_move.mapped('line_ids.analytic_line_ids').unlink()
                                payment_move.write({'state': 'draft', 'is_move_sent': False})
                            payment_move.write({'auto_post': False, 'state': 'cancel'})
                            self.env.cr.execute("RELEASE SAVEPOINT cancel_dn_payment_op")
                            cancelled_dn_payments.append(pay.name or str(pay.id))
                            _logger.info("🔵 [DEBIT_NOTE_V4] Cancelled payment %s (linked to debit note) => DONE", pay.name)
                        except Exception as e:
                            try:
                                self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_dn_payment_op")
                            except Exception:
                                pass
                            _logger.error("🔴 [DEBIT_NOTE_V4] Error cancelling payment %s: %s", pay.name, str(e))

                    if cancelled_dn_payments:
                        messages.append("💰 ยกเลิกใบรับชำระ Debit Note %d ใบ (%s)" %
                                        (len(cancelled_dn_payments), now_thai.strftime('%d/%m/%Y %H:%M:%S')))

            # ✅ อัปเดตสรุปสถานะ
            summary_text = "\n".join(messages) if messages else "ไม่มีรายการที่ถูกยกเลิก"

            # บันทึกสรุปลง sale order โดยใช้ SQL โดยตรง เพื่อหลีกเลี่ยง trigger
            if summary_text:
                existing_summary = self.sale_id.cancel_summary or ""
                if existing_summary:
                    new_summary = existing_summary + "\n\n--- อัปเดตล่าสุด ---\n" + summary_text
                else:
                    new_summary = summary_text

                # ใช้ SQL โดยตรงเพื่ออัปเดต cancel_summary
                self.env.cr.execute("""
                    UPDATE sale_order 
                    SET cancel_summary = %s 
                    WHERE id = %s
                """, (new_summary, self.sale_id.id))

            # Release savepoint ถ้าทุกอย่างสำเร็จ
            self.env.cr.execute("RELEASE SAVEPOINT cancel_operation")

            # แสดงผลลัพธ์การยกเลิก
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('ยกเลิกเรียบร้อย'),
                    'message': _('ดำเนินการยกเลิกรายการที่เลือกเรียบร้อยแล้ว'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            # Rollback to savepoint หากมี error
            try:
                self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_operation")
            except Exception:
                _logger.warning("Savepoint cancel_operation does not exist or already released, skipping rollback")
            _logger.error("Error in cancel operation: %s", str(e))

            # แสดง error message
            raise UserError(_("เกิดข้อผิดพลาดในการยกเลิก: %s") % str(e))