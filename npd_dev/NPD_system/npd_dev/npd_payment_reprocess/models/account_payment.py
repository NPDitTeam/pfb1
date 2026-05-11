# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountPaymentReprocess(models.Model):
    _inherit = 'account.payment'

    allow_reprocess_visible = fields.Boolean(
        string='แสดงปุ่มดำเนินการใหม่',
        compute='_compute_allow_reprocess_visible',
    )

    def _compute_allow_reprocess_visible(self):
        is_allowed = bool(self.env.user.allow_payment_reprocess)
        for rec in self:
            rec.allow_reprocess_visible = is_allowed

    def action_open_reprocess_wizard(self):
        """
        เปิด Wizard popup สำหรับดำเนินการรับชำระใหม่
        (เรียกจากปุ่มบนหน้า Payment เดียว)
        """
        self.ensure_one()

        if not self.env.user.allow_payment_reprocess:
            raise UserError(_("คุณไม่มีสิทธิ์ดำเนินการรับชำระใหม่ กรุณาติดต่อผู้ดูแลระบบ"))

        # สร้าง wizard พร้อมข้อมูล payment ตัวนี้
        wizard = self.env['payment.reprocess.wizard'].create({
            'date_from': self.move_id.write_date or fields.Datetime.now(),
            'date_to': self.move_id.write_date or fields.Datetime.now(),
            'is_searched': True,
        })

        # เพิ่ม line สำหรับ payment ตัวนี้
        cancel_time = self.move_id.write_date if self.move_id else False
        self.env['payment.reprocess.wizard.line'].create({
            'wizard_id': wizard.id,
            'payment_id': self.id,
            'payment_name': self.name or '',
            'move_name': self.move_id.name or '',
            'payment_type': self.payment_type or '',
            'amount': self.amount or 0.0,
            'journal_name': self.journal_id.name or '',
            'cancel_time_thai': str(cancel_time) if cancel_time else '',
            'partner_name': self.partner_id.name or '',
            'selected': True,
        })

        return {
            'name': _('ดำเนินการรับชำระใหม่'),
            'type': 'ir.actions.act_window',
            'res_model': 'payment.reprocess.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_draft(self):
        """
        Override เพื่อข้ามเช็คสิทธิ์เมื่อเรียกจาก Reprocess Wizard
        """
        if self._context.get('skip_draft_permission_check'):
            # ข้ามเช็คสิทธิ์ account_payment_lock_draft_date
            # ทำ logic เดียวกันกับ action_draft เดิม แต่ไม่เช็คสิทธิ์

            # ============ Handle หักเงินประกันค่าเช่า ============
            for invoice_line in self.invoice_ids:
                amount_due = invoice_line.amount_due
                invoice = invoice_line.invoice_id

                has_insurance_deduct = (
                    self.payment_method_one_id.name == 'หักเงินประกันค่าเช่า'
                    or any(
                        line.payment_method_id.name == 'หักเงินประกันค่าเช่า'
                        for line in self.paid_ids
                    )
                )
                if has_insurance_deduct and amount_due <= 0:
                    if invoice:
                        sale_order = self.env['sale.order'].search(
                            [('name', '=', invoice.invoice_origin)], limit=1
                        )
                        if sale_order:
                            picking_related = self.env['stock.picking'].search([
                                ('group_id.name', '=', sale_order.name),
                                ('name', 'like', '%IN%'),
                                ('state', '=', 'done')
                            ], limit=1)
                            if picking_related:
                                sale_order.write({
                                    'rental_status': 'in_rent',
                                    'check_state': '',
                                })
                                picking_related.sudo().write({
                                    'deposit_return_state': 'not_returned'
                                })

            # Reset ผ่าน super ของ base class (account.payment)
            # เรียก super โดยตรงเพื่อข้ามเช็คสิทธิ์
            super(AccountPaymentReprocess, self).action_draft()

            # Reset payment_state ของ invoices
            for invoice_line in self.invoice_ids:
                invoice = invoice_line.invoice_id
                if invoice:
                    try:
                        for line in invoice.line_ids.filtered(
                            lambda l: l.account_id.reconcile and l.reconciled
                        ):
                            line.remove_move_reconcile()
                    except Exception as e:
                        _logger.warning(
                            "⚠️ Unreconcile error for %s: %s" % (invoice.name, str(e))
                        )

                    try:
                        self.env.cr.execute("""
                            UPDATE account_move
                            SET payment_state = 'not_paid'
                            WHERE id = %s
                        """, (invoice.id,))

                        if invoice.move_type in ('out_refund', 'in_refund'):
                            self.env.cr.execute("""
                                UPDATE account_move
                                SET amount_residual = -ABS(amount_total)
                                WHERE id = %s
                            """, (invoice.id,))
                        else:
                            self.env.cr.execute("""
                                UPDATE account_move
                                SET amount_residual = amount_total
                                WHERE id = %s
                            """, (invoice.id,))
                    except Exception as e:
                        _logger.warning(
                            "⚠️ Reset payment_state error for %s: %s" % (
                                invoice.name, str(e)
                            )
                        )

            # ลบ Current Liabilities/Assets lines
            for line in self.move_id.line_ids:
                if line.account_id.user_type_id.name in (
                    'Current Liabilities', 'Current Assets',
                    'สินทรัพย์หมุนเวียน', 'หนี้สินหมุนเวียน'
                ):
                    line.with_context(check_move_validity=False).unlink()

            _logger.info(
                "[Reprocess] ✅ action_draft (skip permission) สำเร็จ: %s" % self.name
            )
            return True

        # ถ้าไม่มี context → เรียก method เดิมตามปกติ
        return super(AccountPaymentReprocess, self).action_draft()
