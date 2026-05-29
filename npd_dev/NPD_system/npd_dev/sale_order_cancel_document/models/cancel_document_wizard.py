from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import datetime, date, timedelta
import pytz

_logger = logging.getLogger(__name__)


def _payment_label(pay):
    """สร้าง label ของ payment สำหรับแสดง/log
    - ถ้า posted แล้วและมี name → ใช้ name
    - ถ้ายังเป็น draft (name=False) → แสดงข้อมูลพอให้รู้ว่าคือใบไหน
    """
    if pay and pay.name:
        return pay.name
    partner = ''
    try:
        partner = (pay.partner_id.name or '') if pay.partner_id else ''
    except Exception:
        partner = ''
    try:
        amt = pay.amount or 0.0
    except Exception:
        amt = 0.0
    return '[ฉบับร่าง #%s %s %.2f บาท]' % (pay.id, partner, amt)


class SaleOrderInheritCancelDoc(models.Model):
    _inherit = 'sale.order'

    # สิทธิ์แสดงปุ่มยกเลิกเอกสาร (อ้างอิงจาก cancel_rent_same_day ของ user)
    show_cancel_document_button = fields.Boolean(
        compute='_compute_show_cancel_document_button',
        store=False,
    )

    def _compute_show_cancel_document_button(self):
        has_right = self.env.user.cancel_rent_same_day
        for rec in self:
            rec.show_cancel_document_button = has_right

    # Fix: field ที่ค้างอยู่ใน view จากโมดูลอื่นที่ถูกลบไปแล้ว
    # ถ้าไม่เพิ่ม field นี้ จะทำให้ติดตั้งโมดูลใหม่ไม่ได้
    freelance_salesperson_id = fields.Many2one(
        'res.partner',
        string='Freelance Salesperson',
        copy=False,
    )

    def action_open_cancel_document_wizard(self):
        """
        เปิด Wizard ยกเลิกเอกสาร
        เงื่อนไข:
        1. เช็ค 3 วันของแต่ละเอกสารตอนกดยืนยัน (ไม่ได้เช็คตอนเปิด wizard)
        2. ถ้า SO ถูกนำไปใช้ในโมดูลคืนเงินประกันค่าเช่า (account.voucher)
           และสถานะ voucher เป็น posted (ยืนยันแล้ว) จะไม่สามารถยกเลิกได้
           แต่ถ้าสถานะเป็น draft (ฉบับร่าง) ยังสามารถยกเลิกได้
        """
        # === เช็คเงื่อนไข account.voucher (คืนเงินประกันค่าเช่า) ===
        if hasattr(self.env['ir.model'], 'search'):
            voucher_model = self.env['ir.model'].search([('model', '=', 'account.voucher')], limit=1)
            if voucher_model:
                vouchers = self.env['account.voucher'].sudo().search([
                    ('reference', '=', self.name),
                    ('state', '!=', 'cancel'),
                ])
                if vouchers:
                    posted_vouchers = vouchers.filtered(lambda v: v.state == 'posted')
                    if posted_vouchers:
                        voucher_names = ', '.join([v.number or v.name or str(v.id) for v in posted_vouchers])
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('ไม่สามารถยกเลิกได้'),
                                'message': _('ใบเช่า %s ถูกนำไปใช้ในเอกสารคืนเงินประกันค่าเช่า (%s) '
                                             'ที่มีสถานะ "ยืนยันแล้ว" ไม่สามารถยกเลิกได้') % (
                                    self.name, voucher_names
                                ),
                                'type': 'danger',
                                'sticky': True,
                            }
                        }
                    _logger.info(
                        "[CANCEL_DOC] SO %s has vouchers in draft state, allowing cancel: %s",
                        self.name, [v.name for v in vouchers]
                    )

        # ดึงเลขเอกสารต่างๆ มาแสดงใน wizard
        # เลข SO
        so_name = self.name or ''

        # เลข Invoice
        invoice_names = ', '.join([inv.name or str(inv.id) for inv in self.invoice_ids if inv.state != 'cancel']) or '-'

        # เลข Delivery (Picking)
        picking_names = ', '.join([p.name for p in self.picking_ids if p.state != 'cancel']) or '-'

        # เลข Insurance (rent_check)
        insurance_names = '-'
        if hasattr(self, 'rent_check'):
            insurance_names = ', '.join([inv.name or str(inv.id) for inv in self.rent_check if inv.state != 'cancel']) or '-'

        # เลข Payment ใบแจ้งหนี้
        pay_inv_list = []
        AccountPayment = self.env['account.payment'].sudo()
        inv_names_only = [inv.name for inv in self.invoice_ids if inv.name]
        for inv_name in inv_names_only:
            pays = AccountPayment.search([('search_invoice_name', '=', inv_name), ('state', '!=', 'cancel')])
            for p in pays:
                if p.name and p.name not in pay_inv_list:
                    pay_inv_list.append(p.name)
        if self.invoice_ids:
            PaymentInvoice = self.env['account.payment.invoice'].sudo()
            pi_lines = PaymentInvoice.search([('invoice_id', 'in', self.invoice_ids.ids)])
            for pi in pi_lines:
                if pi.payment_id and pi.payment_id.state != 'cancel':
                    label = _payment_label(pi.payment_id)
                    if label and label not in pay_inv_list:
                        pay_inv_list.append(label)
        payment_invoice_names = ', '.join(pay_inv_list) or '-'

        # เลข Payment เงินประกัน
        pay_ins_list = []
        if hasattr(self, 'rent_check'):
            ins_names_only = [inv.name for inv in self.rent_check if inv.name]
            for ins_name in ins_names_only:
                pays = AccountPayment.search([('search_invoice_name', '=', ins_name), ('state', '!=', 'cancel')])
                for p in pays:
                    if p.name and p.name not in pay_ins_list:
                        pay_ins_list.append(p.name)
            if self.rent_check:
                PaymentInvoice = self.env['account.payment.invoice'].sudo()
                pi_lines = PaymentInvoice.search([('invoice_id', 'in', self.rent_check.ids)])
                for pi in pi_lines:
                    if pi.payment_id and pi.payment_id.state != 'cancel':
                        label = _payment_label(pi.payment_id)
                        if label and label not in pay_ins_list:
                            pay_ins_list.append(label)
        payment_insurance_names = ', '.join(pay_ins_list) or '-'

        # เลข Debit Note - กรองทั้ง invoice_ids, rent_check (Insurance), และ credit note ออก
        exclude_ids = list(self.invoice_ids.ids)
        if hasattr(self, 'rent_check'):
            exclude_ids += list(self.rent_check.ids)
        debit_notes = self.env['account.move'].sudo().search([
            ('invoice_origin', '=', so_name),
            ('move_type', '=', 'out_invoice'),
            ('id', 'not in', exclude_ids),
            ('state', '!=', 'cancel'),
        ])
        debit_note_names = ', '.join([dn.name or str(dn.id) for dn in debit_notes]) or '-'

        # เลข Credit Note (ใบลดหนี้) - ค้นจาก reversed_entry_id ที่ชี้ไปที่ invoice ของ SO
        all_invoice_ids = list(self.invoice_ids.ids)
        credit_notes = self.env['account.move'].sudo().search([
            ('move_type', '=', 'out_refund'),
            ('reversed_entry_id', 'in', all_invoice_ids),
            ('state', '!=', 'cancel'),
        ])
        # ค้นเพิ่มจาก invoice_origin = SO name
        credit_notes_by_origin = self.env['account.move'].sudo().search([
            ('invoice_origin', '=', so_name),
            ('move_type', '=', 'out_refund'),
            ('id', 'not in', credit_notes.ids),
            ('state', '!=', 'cancel'),
        ])
        credit_notes |= credit_notes_by_origin
        credit_note_names = ', '.join([cn.name or str(cn.id) for cn in credit_notes]) or '-'

        # เลข Payment ของ Debit Note
        dn_pay_names_list = []
        dn_names_for_pay = [dn.name for dn in debit_notes if dn.name]
        if dn_names_for_pay:
            AccountPayment = self.env['account.payment'].sudo()
            for dn_name in dn_names_for_pay:
                pays = AccountPayment.search([
                    ('search_invoice_name', '=', dn_name),
                    ('state', '!=', 'cancel'),
                ])
                for p in pays:
                    if p.name and p.name not in dn_pay_names_list:
                        dn_pay_names_list.append(p.name)
            # ค้นจาก account.payment.invoice ด้วย
            PaymentInvoice = self.env['account.payment.invoice'].sudo()
            pi_lines = PaymentInvoice.search([('invoice_id', 'in', debit_notes.ids)])
            for pi in pi_lines:
                if pi.payment_id and pi.payment_id.state != 'cancel':
                    label = _payment_label(pi.payment_id)
                    if label and label not in dn_pay_names_list:
                        dn_pay_names_list.append(label)
        dn_payment_names = ', '.join(dn_pay_names_list) or '-'

        return {
            'name': 'ยกเลิกเอกสารอ้างอิงบิลเช่า',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.cancel.document.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_id': self.id,
                'default_so_display_name': so_name,
                'default_invoice_display_names': invoice_names,
                'default_delivery_display_names': picking_names,
                'default_insurance_display_names': insurance_names,
                'default_payment_invoice_display_names': payment_invoice_names,
                'default_payment_insurance_display_names': payment_insurance_names,
                'default_debit_note_display_names': debit_note_names,
                'default_debit_note_payment_display_names': dn_payment_names,
                'default_credit_note_display_names': credit_note_names,
            },
        }


class SaleOrderCancelDocumentWizard(models.TransientModel):
    _name = 'sale.order.cancel.document.wizard'
    _description = 'Cancel Related Documents Wizard With Reason'

    sale_id = fields.Many2one('sale.order', required=True, string='ใบเช่าอ้างอิง')

    def _check_date_within_3_days(self, doc_date, doc_name, doc_type_label):
        """ตรวจสอบว่าเอกสารอยู่ภายใน 3 วันหรือไม่ คืน error message ถ้าเกิน"""
        if not doc_date:
            return None
        if isinstance(doc_date, datetime):
            doc_date = doc_date.date()
        today = date.today()
        days_diff = (today - doc_date).days
        if days_diff > 3:
            return '%s %s (วันที่: %s, ผ่านมา %d วัน)' % (
                doc_type_label, doc_name, doc_date.strftime('%d/%m/%Y'), days_diff
            )
        return None

    # === Display document names (readonly) ===
    so_display_name = fields.Char(string='เลขใบเช่า', readonly=True)
    invoice_display_names = fields.Char(string='เลขใบแจ้งหนี้', readonly=True)
    delivery_display_names = fields.Char(string='เลขใบจัดส่งสินค้า', readonly=True)
    insurance_display_names = fields.Char(string='เลขใบรับเงินประกัน', readonly=True)
    payment_invoice_display_names = fields.Char(string='เลขใบรับชำระใบแจ้งหนี้', readonly=True)
    payment_insurance_display_names = fields.Char(string='เลขใบรับชำระเงินประกัน', readonly=True)
    debit_note_display_names = fields.Char(string='เลข Debit Note', readonly=True)
    debit_note_payment_display_names = fields.Char(string='เลขใบรับชำระ Debit Note', readonly=True)
    credit_note_display_names = fields.Char(string='เลขใบลดหนี้', readonly=True)

    # === Checkboxes ===
    cancel_sale_order = fields.Boolean("ยกเลิกใบเช่า")
    cancel_invoice = fields.Boolean("ยกเลิกใบแจ้งหนี้")
    cancel_delivery = fields.Boolean("ยกเลิกใบจัดส่งสินค้า")
    cancel_stock_cut = fields.Boolean("ยกเลิกการตัดสต๊อกสินค้า")
    cancel_insurance = fields.Boolean("ยกเลิกใบแจ้งหนี้รับเงินประกัน")
    cancel_payment_invoice = fields.Boolean("ยกเลิกใบรับชำระใบแจ้งหนี้")
    cancel_payment_insurance = fields.Boolean("ยกเลิกใบรับชำระเงินประกัน")
    cancel_debit_note = fields.Boolean("ยกเลิกใบเพิ่มหนี้ Debit Note")
    cancel_debit_note_payment = fields.Boolean("ยกเลิกใบรับชำระ Debit Note")
    cancel_credit_note = fields.Boolean("ยกเลิกใบลดหนี้")
    select_all = fields.Boolean("เลือกทั้งหมด")

    # === Reason fields (visible when checkbox is ticked) ===
    reason_sale_order = fields.Text(string='เหตุผลยกเลิกใบเช่า')
    reason_invoice = fields.Text(string='เหตุผลยกเลิกใบแจ้งหนี้')
    reason_delivery = fields.Text(string='เหตุผลยกเลิกใบจัดส่งสินค้า')
    reason_stock_cut = fields.Text(string='เหตุผลยกเลิกการตัดสต๊อกสินค้า')
    reason_insurance = fields.Text(string='เหตุผลยกเลิกใบรับเงินประกัน')
    reason_payment_invoice = fields.Text(string='เหตุผลยกเลิกใบรับชำระใบแจ้งหนี้')
    reason_payment_insurance = fields.Text(string='เหตุผลยกเลิกใบรับชำระเงินประกัน')
    reason_debit_note = fields.Text(string='เหตุผลยกเลิกใบเพิ่มหนี้ Debit Note')
    reason_debit_note_payment = fields.Text(string='เหตุผลยกเลิกใบรับชำระ Debit Note')
    reason_credit_note = fields.Text(string='เหตุผลยกเลิกใบลดหนี้')

    @api.onchange('select_all')
    def _onchange_select_all(self):
        val = bool(self.select_all)
        self.cancel_sale_order = val
        self.cancel_invoice = val
        self.cancel_delivery = val
        self.cancel_stock_cut = val
        self.cancel_insurance = val
        self.cancel_payment_invoice = val
        self.cancel_payment_insurance = val
        self.cancel_debit_note = val
        self.cancel_debit_note_payment = val
        self.cancel_credit_note = val

    @api.onchange('cancel_sale_order')
    def _onchange_cancel_sale_order(self):
        if self.cancel_sale_order:
            self.cancel_invoice = True
            self.cancel_delivery = True
            self.cancel_stock_cut = True
            self.cancel_insurance = True
            self.cancel_payment_invoice = True
            self.cancel_payment_insurance = True
            self.cancel_debit_note = True
            self.cancel_debit_note_payment = True
            self.cancel_credit_note = True

    @api.onchange('cancel_invoice', 'cancel_delivery', 'cancel_stock_cut',
                  'cancel_insurance', 'cancel_payment_invoice', 'cancel_payment_insurance',
                  'cancel_debit_note', 'cancel_debit_note_payment', 'cancel_credit_note')
    def _onchange_cancel_options(self):
        all_selected = (self.cancel_sale_order and self.cancel_invoice and
                        self.cancel_delivery and self.cancel_stock_cut and
                        self.cancel_insurance and self.cancel_payment_invoice and
                        self.cancel_payment_insurance and self.cancel_debit_note and
                        self.cancel_debit_note_payment and self.cancel_credit_note)
        if all_selected:
            self.select_all = True
        else:
            self.select_all = False

    # ========== Stock helper methods (same logic as original module) ==========

    def _is_return_picking(self, picking):
        return any(m.origin_returned_move_id for m in picking.move_lines)

    def _has_been_returned(self, picking):
        for move in picking.move_lines.filtered(lambda m: m.state == 'done'):
            returned_done = move.returned_move_ids.filtered(lambda rm: rm.state == 'done')
            if returned_done:
                return True
        return False

    def _handle_stock_return(self, picking, tz):
        messages = []
        now_thai = datetime.now(tz)

        if picking.state == 'done':
            picking_type = picking.picking_type_id.code if picking.picking_type_id else 'N/A'
            has_returned = self._has_been_returned(picking)

            if picking_type == 'incoming':
                messages.append(
                    "ข้าม %s (เป็นใบรับสินค้าเข้า ไม่ต้องคืนซ้ำ) (%s)" %
                    (picking.name, now_thai.strftime('%d/%m/%Y %H:%M:%S'))
                )
                return messages

            if has_returned:
                messages.append(
                    "ข้าม %s (คืนสต๊อกไปแล้วก่อนหน้านี้) (%s)" %
                    (picking.name, now_thai.strftime('%d/%m/%Y %H:%M:%S'))
                )
                return messages

            done_moves = picking.move_lines.filtered(lambda m: m.state == 'done' and m.quantity_done > 0)
            if done_moves:
                try:
                    return_wiz = self.env['stock.return.picking'].with_context(active_id=picking.id).create({
                        'picking_id': picking.id,
                        'location_id': picking.location_id.id,
                        'product_return_moves': [(0, 0, {
                            'product_id': move.product_id.id,
                            'quantity': move.quantity_done,
                            'move_id': move.id,
                        }) for move in done_moves],
                    })
                    return_action = return_wiz.create_returns()
                    return_pick_id = return_action.get('res_id')

                    if return_pick_id:
                        return_pick = self.env['stock.picking'].browse(return_pick_id)
                        return_pick.action_confirm()
                        return_pick.action_assign()

                        for move_line in return_pick.move_lines:
                            move_line.quantity_done = move_line.product_uom_qty
                        for sml in return_pick.move_line_ids:
                            if sml.qty_done == 0:
                                sml.qty_done = sml.product_uom_qty

                        validate_result = return_pick.sudo().button_validate()

                        if isinstance(validate_result, dict) and validate_result.get('res_model'):
                            wizard_model = validate_result.get('res_model')
                            if wizard_model == 'stock.immediate.transfer':
                                immediate_wiz = self.env['stock.immediate.transfer'].create({
                                    'pick_ids': [(6, 0, [return_pick.id])],
                                })
                                immediate_wiz.process()
                            elif wizard_model == 'stock.backorder.confirmation':
                                backorder_wiz = self.env['stock.backorder.confirmation'].create({
                                    'pick_ids': [(6, 0, [return_pick.id])],
                                })
                                backorder_wiz.process()

                        return_pick.invalidate_cache()

                        if return_pick.state == 'done':
                            messages.append(
                                "คืนสต๊อก %s เรียบร้อย (คืน %d รายการ) (%s)" %
                                (picking.name, len(done_moves), now_thai.strftime('%d/%m/%Y %H:%M:%S'))
                            )
                        else:
                            messages.append(
                                "คืนสต๊อก %s สร้างใบคืนแล้ว (%s) สถานะ: %s (%s)" %
                                (picking.name, return_pick.name, return_pick.state, now_thai.strftime('%d/%m/%Y %H:%M:%S'))
                            )
                except Exception as e:
                    _logger.error("Error returning stock for picking %s: %s", picking.name, str(e))
                    messages.append("ไม่สามารถคืนสต๊อก %s: %s" % (picking.name, str(e)))

        elif picking.state not in ['cancel']:
            picking.action_cancel()
            messages.append(
                "ยกเลิก %s ที่รอดำเนินการ (%s)" %
                (picking.name, now_thai.strftime('%d/%m/%Y %H:%M:%S'))
            )
        return messages

    # ========== Main confirm action ==========

    def confirm_cancel(self):
        """ยกเลิกเอกสารที่เลือก พร้อมบันทึกเหตุผล และสร้าง Log"""
        # ตรวจสอบว่าเลือกอะไรบ้าง
        selected = []
        if self.cancel_sale_order:
            selected.append('sale_order')
        if self.cancel_invoice:
            selected.append('invoice')
        if self.cancel_delivery:
            selected.append('delivery')
        if self.cancel_stock_cut:
            selected.append('stock_cut')
        if self.cancel_insurance:
            selected.append('insurance')
        if self.cancel_payment_invoice:
            selected.append('payment_invoice')
        if self.cancel_payment_insurance:
            selected.append('payment_insurance')
        if self.cancel_debit_note:
            selected.append('debit_note')
        if self.cancel_debit_note_payment:
            selected.append('debit_note_payment')
        if self.cancel_credit_note:
            selected.append('credit_note')

        if not selected:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('กรุณาเลือกรายการ'),
                    'message': _('กรุณาเลือกรายการที่ต้องการยกเลิกอย่างน้อย 1 รายการ'),
                    'type': 'warning',
                }
            }

        # ตรวจสอบเหตุผล - บังคับกรอกถ้าติ๊ก
        reason_map = {
            'sale_order': ('cancel_sale_order', 'reason_sale_order', 'ใบเช่า'),
            'invoice': ('cancel_invoice', 'reason_invoice', 'ใบแจ้งหนี้'),
            'delivery': ('cancel_delivery', 'reason_delivery', 'ใบจัดส่งสินค้า'),
            'stock_cut': ('cancel_stock_cut', 'reason_stock_cut', 'การตัดสต๊อกสินค้า'),
            'insurance': ('cancel_insurance', 'reason_insurance', 'ใบรับเงินประกัน'),
            'payment_invoice': ('cancel_payment_invoice', 'reason_payment_invoice', 'ใบรับชำระใบแจ้งหนี้'),
            'payment_insurance': ('cancel_payment_insurance', 'reason_payment_insurance', 'ใบรับชำระเงินประกัน'),
            'debit_note': ('cancel_debit_note', 'reason_debit_note', 'ใบเพิ่มหนี้ Debit Note'),
            'debit_note_payment': ('cancel_debit_note_payment', 'reason_debit_note_payment', 'ใบรับชำระ Debit Note'),
            'credit_note': ('cancel_credit_note', 'reason_credit_note', 'ใบลดหนี้'),
        }

        missing_reasons = []
        for key in selected:
            checkbox_field, reason_field, label = reason_map[key]
            reason_value = getattr(self, reason_field, False)
            if not reason_value or not reason_value.strip():
                missing_reasons.append(label)

        if missing_reasons:
            raise UserError(
                _('กรุณาระบุเหตุผลในการยกเลิกสำหรับ:\n- %s') % '\n- '.join(missing_reasons)
            )

        # ===== เตรียมข้อมูลพื้นฐาน =====
        so_name = self.sale_id.name
        messages = []
        tz = pytz.timezone('Asia/Bangkok')
        now_thai = datetime.now(tz)
        log_model = self.env['cancelled.document.log']

        # เตรียมข้อมูล invoice names สำหรับค้น payment
        invoice_names = [inv.name for inv in self.sale_id.invoice_ids if inv.name]
        if hasattr(self.sale_id, 'rent_check'):
            for inv in self.sale_id.rent_check:
                if inv.name and inv.name not in invoice_names:
                    invoice_names.append(inv.name)

        all_moves_by_so = self.env['account.move'].sudo().search([
            ('invoice_origin', '=', so_name),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('id', 'not in', self.sale_id.invoice_ids.ids),
        ])
        for mv in all_moves_by_so:
            if mv.name and mv.name not in invoice_names:
                invoice_names.append(mv.name)

        # branch_id ของ User ที่กดยกเลิก (ใช้สำหรับ filter ตามสาขา)
        user_branch_id = self.env.user.branch_id.id if self.env.user.branch_id else False

        # === เช็ค 3 วันของแต่ละเอกสารที่เลือก ===
        over_3_days = []

        if self.cancel_sale_order:
            err = self._check_date_within_3_days(
                self.sale_id.date_order, self.sale_id.name, 'ใบเช่า')
            if err:
                over_3_days.append(err)

        if self.cancel_invoice:
            for inv in self.sale_id.invoice_ids.filtered(lambda i: i.state != 'cancel'):
                err = self._check_date_within_3_days(
                    inv.invoice_date or inv.date, inv.name or str(inv.id), 'ใบแจ้งหนี้')
                if err:
                    over_3_days.append(err)

        if self.cancel_delivery and not self.cancel_sale_order:
            for pick in self.sale_id.picking_ids.filtered(lambda p: p.state not in ['cancel', 'done']):
                err = self._check_date_within_3_days(
                    pick.scheduled_date, pick.name, 'ใบจัดส่ง')
                if err:
                    over_3_days.append(err)

        if self.cancel_insurance and hasattr(self.sale_id, 'rent_check'):
            for inv in self.sale_id.rent_check.filtered(lambda i: i.state != 'cancel'):
                err = self._check_date_within_3_days(
                    inv.invoice_date or inv.date, inv.name or str(inv.id), 'ใบรับเงินประกัน')
                if err:
                    over_3_days.append(err)

        if self.cancel_debit_note or self.cancel_credit_note:
            exclude_ids = list(self.sale_id.invoice_ids.ids)
            if hasattr(self.sale_id, 'rent_check'):
                exclude_ids += list(self.sale_id.rent_check.ids)
            if self.cancel_debit_note:
                dns = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so_name), ('move_type', '=', 'out_invoice'),
                    ('id', 'not in', exclude_ids), ('state', '!=', 'cancel'),
                ])
                for dn in dns:
                    err = self._check_date_within_3_days(
                        dn.invoice_date or dn.date, dn.name or str(dn.id), 'Debit Note')
                    if err:
                        over_3_days.append(err)
            if self.cancel_credit_note:
                cns = self.env['account.move'].sudo().search([
                    ('move_type', '=', 'out_refund'),
                    '|', ('reversed_entry_id', 'in', self.sale_id.invoice_ids.ids),
                    ('invoice_origin', '=', so_name),
                    ('state', '!=', 'cancel'),
                ])
                for cn in cns:
                    err = self._check_date_within_3_days(
                        cn.invoice_date or cn.date, cn.name or str(cn.id), 'ใบลดหนี้')
                    if err:
                        over_3_days.append(err)

        if self.cancel_payment_invoice:
            # เช็ค 3 วัน payment ของใบแจ้งหนี้
            AccountPayment = self.env['account.payment'].sudo()
            inv_names_only = [inv.name for inv in self.sale_id.invoice_ids if inv.name]
            chk_pay_inv = AccountPayment
            for inv_name in inv_names_only:
                pays = AccountPayment.search([('search_invoice_name', '=', inv_name), ('state', '!=', 'cancel')])
                chk_pay_inv |= pays
            if self.sale_id.invoice_ids:
                PaymentInvoice = self.env['account.payment.invoice'].sudo()
                pi_lines = PaymentInvoice.search([('invoice_id', 'in', self.sale_id.invoice_ids.ids)])
                for pi in pi_lines:
                    if pi.payment_id and pi.payment_id.state != 'cancel':
                        chk_pay_inv |= pi.payment_id
            for pay in chk_pay_inv:
                err = self._check_date_within_3_days(pay.date, pay.name or str(pay.id), 'ใบรับชำระใบแจ้งหนี้')
                if err:
                    over_3_days.append(err)

        if self.cancel_payment_insurance:
            # เช็ค 3 วัน payment ของเงินประกัน
            AccountPayment = self.env['account.payment'].sudo()
            chk_pay_ins = AccountPayment
            if hasattr(self.sale_id, 'rent_check'):
                ins_names = [inv.name for inv in self.sale_id.rent_check if inv.name]
                for ins_name in ins_names:
                    pays = AccountPayment.search([('search_invoice_name', '=', ins_name), ('state', '!=', 'cancel')])
                    chk_pay_ins |= pays
                if self.sale_id.rent_check:
                    PaymentInvoice = self.env['account.payment.invoice'].sudo()
                    pi_lines = PaymentInvoice.search([('invoice_id', 'in', self.sale_id.rent_check.ids)])
                    for pi in pi_lines:
                        if pi.payment_id and pi.payment_id.state != 'cancel':
                            chk_pay_ins |= pi.payment_id
            for pay in chk_pay_ins:
                err = self._check_date_within_3_days(pay.date, pay.name or str(pay.id), 'ใบรับชำระเงินประกัน')
                if err:
                    over_3_days.append(err)

        if self.cancel_debit_note_payment:
            # ค้นหา payment ของ debit note เพื่อเช็ค 3 วัน
            exclude_ids_chk = list(self.sale_id.invoice_ids.ids)
            if hasattr(self.sale_id, 'rent_check'):
                exclude_ids_chk += list(self.sale_id.rent_check.ids)
            dn_for_chk = self.env['account.move'].sudo().search([
                ('invoice_origin', '=', so_name),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('id', 'not in', exclude_ids_chk),
            ])
            dn_names_chk = [dn.name for dn in dn_for_chk if dn.name]
            if dn_names_chk:
                AccountPayment = self.env['account.payment'].sudo()
                for dn_name in dn_names_chk:
                    pays = AccountPayment.search([
                        ('search_invoice_name', '=', dn_name),
                        ('state', '!=', 'cancel'),
                    ])
                    for pay in pays:
                        err = self._check_date_within_3_days(
                            pay.date, pay.name or str(pay.id), 'ใบรับชำระ Debit Note')
                        if err:
                            over_3_days.append(err)

        if over_3_days:
            raise UserError(
                _('ไม่สามารถยกเลิกเอกสารต่อไปนี้ได้ เนื่องจากเกิน 3 วัน:\n- %s') % '\n- '.join(over_3_days)
            )

        try:
            self.env.cr.execute("SAVEPOINT cancel_doc_operation")

            # ---- 1. ยกเลิกใบเช่า ----
            if self.cancel_sale_order:
                stock_messages = []
                for picking in self.sale_id.picking_ids:
                    stock_msg = self._handle_stock_return(picking, tz)
                    stock_messages.extend(stock_msg)

                if self.sale_id.state not in ['cancel', 'done']:
                    try:
                        self.env.cr.execute("""
                            UPDATE sale_order SET state = 'cancel' WHERE id = %s
                        """, (self.sale_id.id,))
                        self.sale_id.invalidate_cache(['state'], [self.sale_id.id])
                        messages.append("ยกเลิกใบเช่า %s เรียบร้อย" % self.sale_id.name)

                        # สร้าง Log
                        log_vals = {
                            'sale_order_id': self.sale_id.id,
                            'document_type': 'sale_order',
                            'document_name': self.sale_id.name,
                            'reason': self.reason_sale_order,
                            'cancelled_by': self.env.user.id,
                            'cancelled_date': fields.Datetime.now(),
                            'branch_id': user_branch_id,
                        }
                        _logger.info("[CANCEL_DOC_LOG] Creating log: %s", log_vals)
                        new_log = log_model.sudo().create(log_vals)
                        _logger.info("[CANCEL_DOC_LOG] Created log ID: %s", new_log.id)
                    except Exception as e:
                        _logger.error("[CANCEL_DOC_LOG] Error cancelling sale order %s: %s", self.sale_id.name, str(e))
                        messages.append("ไม่สามารถยกเลิกใบเช่า %s: %s" % (self.sale_id.name, str(e)))
                elif self.sale_id.state == 'done':
                    messages.append("ใบเช่า %s อยู่ในสถานะ done ไม่สามารถยกเลิกได้" % self.sale_id.name)
                else:
                    messages.append("ใบเช่า %s ยกเลิกไปแล้วก่อนหน้านี้" % self.sale_id.name)

            # ---- 2. ยกเลิกใบแจ้งหนี้ ----
            if self.cancel_invoice:
                for invoice in self.sale_id.invoice_ids:
                    if invoice.state != 'cancel':
                        try:
                            self.env.cr.execute("SAVEPOINT cancel_inv_op")
                            inv = invoice.sudo()
                            if inv.state == 'posted':
                                reconciled_lines = inv.line_ids.filtered(
                                    lambda l: l.account_id.reconcile and l.reconciled
                                )
                                if reconciled_lines:
                                    reconciled_lines.remove_move_reconcile()
                                inv.mapped('line_ids.analytic_line_ids').unlink()
                                inv.write({'state': 'draft', 'is_move_sent': False})
                            inv.write({'auto_post': False, 'state': 'cancel'})
                            self.env.cr.execute("RELEASE SAVEPOINT cancel_inv_op")
                            messages.append("ยกเลิกใบแจ้งหนี้ %s เรียบร้อย" % (invoice.name or str(invoice.id)))

                            log_model.sudo().create({
                                'sale_order_id': self.sale_id.id,
                                'document_type': 'invoice',
                                'document_name': invoice.name or str(invoice.id),
                                'reason': self.reason_invoice,
                                'cancelled_by': self.env.user.id,
                                'cancelled_date': fields.Datetime.now(),
                                'branch_id': user_branch_id,
                            })
                        except Exception as e:
                            self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_inv_op")
                            messages.append("ไม่สามารถยกเลิกใบแจ้งหนี้ %s: %s" % (invoice.name or str(invoice.id), str(e)))

            # ---- 3. ยกเลิกใบจัดส่งสินค้า ----
            if self.cancel_delivery and not self.cancel_sale_order:
                for picking in self.sale_id.picking_ids:
                    if picking.state not in ['cancel', 'done']:
                        try:
                            self.env.cr.execute("SAVEPOINT cancel_del_op")
                            picking.sudo().action_cancel()
                            self.env.cr.execute("RELEASE SAVEPOINT cancel_del_op")
                            messages.append("ยกเลิกใบจัดส่ง %s เรียบร้อย" % picking.name)

                            log_model.sudo().create({
                                'sale_order_id': self.sale_id.id,
                                'document_type': 'delivery',
                                'document_name': picking.name,
                                'reason': self.reason_delivery,
                                'cancelled_by': self.env.user.id,
                                'cancelled_date': fields.Datetime.now(),
                                'branch_id': user_branch_id,
                            })
                        except Exception as e:
                            self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_del_op")
                            messages.append("ไม่สามารถยกเลิกใบจัดส่ง %s: %s" % (picking.name, str(e)))

            # ---- 4. ยกเลิกการตัดสต๊อก ----
            if self.cancel_stock_cut and not self.cancel_sale_order:
                done_pickings = self.sale_id.picking_ids.filtered(lambda p: p.state == 'done')
                if done_pickings:
                    for picking in done_pickings:
                        stock_msg = self._handle_stock_return(picking, tz)
                        messages.extend(stock_msg)

                    log_model.sudo().create({
                        'sale_order_id': self.sale_id.id,
                        'document_type': 'stock_cut',
                        'document_name': ', '.join([p.name for p in done_pickings]),
                        'reason': self.reason_stock_cut,
                        'cancelled_by': self.env.user.id,
                        'cancelled_date': fields.Datetime.now(),
                        'branch_id': user_branch_id,
                    })
                else:
                    messages.append("ไม่พบรายการตัดสต๊อกที่ต้องคืน")

            # ---- 5. ยกเลิกใบรับเงินประกัน ----
            if self.cancel_insurance:
                if hasattr(self.sale_id, 'rent_check'):
                    for inv in self.sale_id.rent_check:
                        if inv.state != 'cancel':
                            try:
                                self.env.cr.execute("SAVEPOINT cancel_ins_op")
                                ins = inv.sudo()
                                if ins.state == 'posted':
                                    reconciled_lines = ins.line_ids.filtered(
                                        lambda l: l.account_id.reconcile and l.reconciled
                                    )
                                    if reconciled_lines:
                                        reconciled_lines.remove_move_reconcile()
                                    ins.mapped('line_ids.analytic_line_ids').unlink()
                                    ins.write({'state': 'draft', 'is_move_sent': False})
                                ins.write({'auto_post': False, 'state': 'cancel'})
                                self.env.cr.execute("RELEASE SAVEPOINT cancel_ins_op")
                                messages.append("ยกเลิกใบรับเงินประกัน %s เรียบร้อย" % (inv.name or str(inv.id)))

                                log_model.sudo().create({
                                    'sale_order_id': self.sale_id.id,
                                    'document_type': 'insurance',
                                    'document_name': inv.name or str(inv.id),
                                    'reason': self.reason_insurance,
                                    'cancelled_by': self.env.user.id,
                                    'cancelled_date': fields.Datetime.now(),
                                    'branch_id': user_branch_id,
                                })
                            except Exception as e:
                                self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_ins_op")
                                messages.append("ไม่สามารถยกเลิกใบรับเงินประกัน %s: %s" % (inv.name or str(inv.id), str(e)))

            # ---- 6a. ยกเลิกใบรับชำระใบแจ้งหนี้ ----
            if self.cancel_payment_invoice:
                AccountPayment = self.env['account.payment'].sudo()
                found_pay_inv = AccountPayment
                inv_names_only = [inv.name for inv in self.sale_id.invoice_ids if inv.name]
                for inv_name in inv_names_only:
                    pays = AccountPayment.search([('search_invoice_name', '=', inv_name), ('state', '!=', 'cancel')])
                    found_pay_inv |= pays
                if self.sale_id.invoice_ids:
                    PaymentInvoice = self.env['account.payment.invoice'].sudo()
                    pi_lines = PaymentInvoice.search([('invoice_id', 'in', self.sale_id.invoice_ids.ids)])
                    for pi in pi_lines:
                        if pi.payment_id and pi.payment_id.state != 'cancel':
                            found_pay_inv |= pi.payment_id

                for pay in found_pay_inv:
                    pay_label = _payment_label(pay)
                    try:
                        self.env.cr.execute("SAVEPOINT cancel_payinv_op")
                        payment_move = pay.move_id
                        if pay.state == 'draft':
                            # Payment ฉบับร่าง: ยังไม่ใช่เอกสารทางบัญชี → set state เป็น cancel โดยตรง
                            if payment_move and payment_move.state != 'cancel':
                                payment_move.write({'auto_post': False, 'state': 'cancel'})
                            try:
                                pay.sudo().write({'state': 'cancel'})
                            except Exception:
                                pass
                        else:
                            if pay.state == 'posted':
                                reconciled_lines = payment_move.line_ids.filtered(lambda l: l.account_id.reconcile and l.reconciled)
                                if reconciled_lines:
                                    reconciled_lines.remove_move_reconcile()
                                payment_move.mapped('line_ids.analytic_line_ids').unlink()
                                payment_move.write({'state': 'draft', 'is_move_sent': False})
                            payment_move.write({'auto_post': False, 'state': 'cancel'})
                        self.env.cr.execute("RELEASE SAVEPOINT cancel_payinv_op")
                        messages.append("ยกเลิกใบรับชำระใบแจ้งหนี้ %s เรียบร้อย" % pay_label)
                        log_model.sudo().create({
                            'sale_order_id': self.sale_id.id,
                            'document_type': 'payment_invoice',
                            'document_name': pay_label,
                            'reason': self.reason_payment_invoice,
                            'cancelled_by': self.env.user.id,
                            'cancelled_date': fields.Datetime.now(),
                            'branch_id': user_branch_id,
                        })
                    except Exception as e:
                        try:
                            self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_payinv_op")
                        except Exception:
                            pass
                        messages.append("ไม่สามารถยกเลิกใบรับชำระใบแจ้งหนี้ %s: %s" % (pay_label, str(e)))

            # ---- 6b. ยกเลิกใบรับชำระเงินประกัน ----
            if self.cancel_payment_insurance:
                AccountPayment = self.env['account.payment'].sudo()
                found_pay_ins = AccountPayment
                if hasattr(self.sale_id, 'rent_check'):
                    ins_names = [inv.name for inv in self.sale_id.rent_check if inv.name]
                    for ins_name in ins_names:
                        pays = AccountPayment.search([('search_invoice_name', '=', ins_name), ('state', '!=', 'cancel')])
                        found_pay_ins |= pays
                    if self.sale_id.rent_check:
                        PaymentInvoice = self.env['account.payment.invoice'].sudo()
                        pi_lines = PaymentInvoice.search([('invoice_id', 'in', self.sale_id.rent_check.ids)])
                        for pi in pi_lines:
                            if pi.payment_id and pi.payment_id.state != 'cancel':
                                found_pay_ins |= pi.payment_id

                for pay in found_pay_ins:
                    pay_label = _payment_label(pay)
                    try:
                        self.env.cr.execute("SAVEPOINT cancel_payins_op")
                        payment_move = pay.move_id
                        if pay.state == 'draft':
                            # Payment ฉบับร่าง: ยังไม่ใช่เอกสารทางบัญชี → set state เป็น cancel โดยตรง
                            if payment_move and payment_move.state != 'cancel':
                                payment_move.write({'auto_post': False, 'state': 'cancel'})
                            try:
                                pay.sudo().write({'state': 'cancel'})
                            except Exception:
                                pass
                        else:
                            if pay.state == 'posted':
                                reconciled_lines = payment_move.line_ids.filtered(lambda l: l.account_id.reconcile and l.reconciled)
                                if reconciled_lines:
                                    reconciled_lines.remove_move_reconcile()
                                payment_move.mapped('line_ids.analytic_line_ids').unlink()
                                payment_move.write({'state': 'draft', 'is_move_sent': False})
                            payment_move.write({'auto_post': False, 'state': 'cancel'})
                        self.env.cr.execute("RELEASE SAVEPOINT cancel_payins_op")
                        messages.append("ยกเลิกใบรับชำระเงินประกัน %s เรียบร้อย" % pay_label)
                        log_model.sudo().create({
                            'sale_order_id': self.sale_id.id,
                            'document_type': 'payment_insurance',
                            'document_name': pay_label,
                            'reason': self.reason_payment_insurance,
                            'cancelled_by': self.env.user.id,
                            'cancelled_date': fields.Datetime.now(),
                            'branch_id': user_branch_id,
                        })
                    except Exception as e:
                        try:
                            self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_payins_op")
                        except Exception:
                            pass
                        messages.append("ไม่สามารถยกเลิกใบรับชำระเงินประกัน %s: %s" % (pay_label, str(e)))

            # ---- 7. ยกเลิก Debit Note ----
            if self.cancel_debit_note:
                # กรองทั้ง invoice_ids และ rent_check (Insurance) ออก
                exclude_ids = list(self.sale_id.invoice_ids.ids)
                if hasattr(self.sale_id, 'rent_check'):
                    exclude_ids += list(self.sale_id.rent_check.ids)
                all_debit_notes = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so_name),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('id', 'not in', exclude_ids),
                    ('state', '!=', 'cancel'),
                ])

                for dn in all_debit_notes:
                    try:
                        self.env.cr.execute("SAVEPOINT cancel_dn_op")
                        if dn.state == 'posted':
                            reconciled_lines = dn.line_ids.filtered(
                                lambda l: l.account_id.reconcile and l.reconciled
                            )
                            if reconciled_lines:
                                reconciled_lines.remove_move_reconcile()
                            dn.mapped('line_ids.analytic_line_ids').unlink()
                            dn.write({'state': 'draft', 'is_move_sent': False})
                        dn.write({'auto_post': False, 'state': 'cancel'})
                        self.env.cr.execute("RELEASE SAVEPOINT cancel_dn_op")
                        messages.append("ยกเลิก Debit Note %s เรียบร้อย" % (dn.name or str(dn.id)))

                        log_model.sudo().create({
                            'sale_order_id': self.sale_id.id,
                            'document_type': 'debit_note',
                            'document_name': dn.name or str(dn.id),
                            'reason': self.reason_debit_note,
                            'cancelled_by': self.env.user.id,
                            'cancelled_date': fields.Datetime.now(),
                            'branch_id': user_branch_id,
                        })
                    except Exception as e:
                        try:
                            self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_dn_op")
                        except Exception:
                            pass
                        messages.append("ไม่สามารถยกเลิก Debit Note %s: %s" % (dn.name or str(dn.id), str(e)))

            # ---- 7.5 ยกเลิกใบรับชำระ Debit Note (แยกจาก cancel_debit_note) ----
            if self.cancel_debit_note_payment:
                # ค้นหา debit notes ก่อน
                exclude_ids_dnp = list(self.sale_id.invoice_ids.ids)
                if hasattr(self.sale_id, 'rent_check'):
                    exclude_ids_dnp += list(self.sale_id.rent_check.ids)
                all_dn_for_pay = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so_name),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('id', 'not in', exclude_ids_dnp),
                ])
                dn_names = [dn.name for dn in all_dn_for_pay if dn.name]
                if dn_names:
                    AccountPayment = self.env['account.payment'].sudo()
                    dn_payments = AccountPayment
                    for dn_name in dn_names:
                        pays = AccountPayment.search([
                            ('search_invoice_name', '=', dn_name),
                            ('state', '!=', 'cancel'),
                        ])
                        dn_payments |= pays

                    PaymentInvoice = self.env['account.payment.invoice'].sudo()
                    pi_lines = PaymentInvoice.search([('invoice_id', 'in', all_debit_notes.ids)])
                    for pi in pi_lines:
                        if pi.payment_id and pi.payment_id.state != 'cancel':
                            dn_payments |= pi.payment_id

                    for pay in dn_payments:
                        pay_label = _payment_label(pay)
                        try:
                            self.env.cr.execute("SAVEPOINT cancel_dnpay_op")
                            payment_move = pay.move_id
                            if pay.state == 'draft':
                                # Payment ฉบับร่าง: ยังไม่ใช่เอกสารทางบัญชี → set state เป็น cancel โดยตรง
                                if payment_move and payment_move.state != 'cancel':
                                    payment_move.write({'auto_post': False, 'state': 'cancel'})
                                try:
                                    pay.sudo().write({'state': 'cancel'})
                                except Exception:
                                    pass
                            else:
                                if pay.state == 'posted':
                                    reconciled_lines = payment_move.line_ids.filtered(
                                        lambda l: l.account_id.reconcile and l.reconciled
                                    )
                                    if reconciled_lines:
                                        reconciled_lines.remove_move_reconcile()
                                    payment_move.mapped('line_ids.analytic_line_ids').unlink()
                                    payment_move.write({'state': 'draft', 'is_move_sent': False})
                                payment_move.write({'auto_post': False, 'state': 'cancel'})
                            self.env.cr.execute("RELEASE SAVEPOINT cancel_dnpay_op")
                            messages.append("ยกเลิกใบรับชำระ Debit Note %s เรียบร้อย" % pay_label)

                            log_model.sudo().create({
                                'sale_order_id': self.sale_id.id,
                                'document_type': 'debit_note_payment',
                                'document_name': pay_label,
                                'reason': self.reason_debit_note,
                                'cancelled_by': self.env.user.id,
                                'cancelled_date': fields.Datetime.now(),
                                'branch_id': user_branch_id,
                            })
                        except Exception as e:
                            try:
                                self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_dnpay_op")
                            except Exception:
                                pass

            # ---- 8. ยกเลิกใบลดหนี้ (Credit Note) ----
            if self.cancel_credit_note:
                all_invoice_ids = list(self.sale_id.invoice_ids.ids)
                # ค้นจาก reversed_entry_id ที่ชี้ไปที่ invoice ของ SO
                credit_notes = self.env['account.move'].sudo().search([
                    ('move_type', '=', 'out_refund'),
                    ('reversed_entry_id', 'in', all_invoice_ids),
                    ('state', '!=', 'cancel'),
                ])
                # ค้นเพิ่มจาก invoice_origin = SO name
                credit_notes_by_origin = self.env['account.move'].sudo().search([
                    ('invoice_origin', '=', so_name),
                    ('move_type', '=', 'out_refund'),
                    ('id', 'not in', credit_notes.ids),
                    ('state', '!=', 'cancel'),
                ])
                credit_notes |= credit_notes_by_origin

                for cn in credit_notes:
                    try:
                        self.env.cr.execute("SAVEPOINT cancel_cn_op")
                        if cn.state == 'posted':
                            reconciled_lines = cn.line_ids.filtered(
                                lambda l: l.account_id.reconcile and l.reconciled
                            )
                            if reconciled_lines:
                                reconciled_lines.remove_move_reconcile()
                            cn.mapped('line_ids.analytic_line_ids').unlink()
                            cn.write({'state': 'draft', 'is_move_sent': False})
                        cn.write({'auto_post': False, 'state': 'cancel'})
                        self.env.cr.execute("RELEASE SAVEPOINT cancel_cn_op")
                        messages.append("ยกเลิกใบลดหนี้ %s เรียบร้อย" % (cn.name or str(cn.id)))

                        log_model.sudo().create({
                            'sale_order_id': self.sale_id.id,
                            'document_type': 'credit_note',
                            'document_name': cn.name or str(cn.id),
                            'reason': self.reason_credit_note,
                            'cancelled_by': self.env.user.id,
                            'cancelled_date': fields.Datetime.now(),
                            'branch_id': user_branch_id,
                        })
                    except Exception as e:
                        try:
                            self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_cn_op")
                        except Exception:
                            pass
                        messages.append("ไม่สามารถยกเลิกใบลดหนี้ %s: %s" % (cn.name or str(cn.id), str(e)))

            # Release savepoint
            self.env.cr.execute("RELEASE SAVEPOINT cancel_doc_operation")

            summary = '\n'.join(messages) if messages else 'ไม่มีรายการที่ถูกยกเลิก'
            _logger.info("[CANCEL_DOC] Result: %s", summary)

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
            try:
                self.env.cr.execute("ROLLBACK TO SAVEPOINT cancel_doc_operation")
            except Exception:
                pass
            _logger.error("Error in cancel document operation: %s", str(e))
            raise UserError(_("เกิดข้อผิดพลาดในการยกเลิก: %s") % str(e))
