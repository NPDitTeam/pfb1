# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentDebtTracking(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        """Override action_post เพื่อเช็คและอัปเดตยอดชำระใน npd.debt.tracking"""
        # เรียก super() ก่อน
        res = super(AccountPaymentDebtTracking, self).action_post()
        
        # หลังจาก post สำเร็จ ให้เช็คและอัปเดต npd.debt.tracking
        self._update_debt_tracking_payment()
        
        return res

    def action_draft(self):
        """Override action_draft เพื่อเคลียร์ยอดชำระใน npd.debt.tracking"""
        # เคลียร์ยอดใน npd.debt.tracking ก่อน
        self._clear_debt_tracking_payment()
        
        # เรียก super()
        return super(AccountPaymentDebtTracking, self).action_draft()

    def _update_debt_tracking_payment(self):
        """
        เช็คใบแจ้งหนี้จาก search_invoice_name กับ npd.debt.tracking.invoice_id
        ถ้าสถานะเป็น done ให้อัปเดตยอดชำระ
        """
        for payment in self:
            if not payment.search_invoice_name:
                continue

            # แยกเลขใบแจ้งหนี้ (อาจมีหลายใบคั่นด้วย comma)
            invoice_names = [name.strip() for name in payment.search_invoice_name.split(',')]
            
            _logger.info(f"🔍 ตรวจสอบใบแจ้งหนี้: {invoice_names} สำหรับ Payment: {payment.name}")
            
            for invoice_name in invoice_names:
                # หา account.move จากชื่อใบแจ้งหนี้
                invoice = self.env['account.move'].search([
                    ('name', '=', invoice_name)
                ], limit=1)
                
                if not invoice:
                    _logger.warning(f"⚠️ ไม่พบใบแจ้งหนี้: {invoice_name}")
                    continue
                
                # หา npd.debt.tracking ที่มี invoice_id ตรงกัน และสถานะเป็น done
                debt_tracking = self.env['npd.debt.tracking'].search([
                    ('invoice_id', '=', invoice.id),
                    ('state', '=', 'done')
                ], limit=1)
                
                if debt_tracking:
                    # อัปเดตยอดชำระ พร้อมผู้ล็อกอิน
                    current_user = self.env.user
                    debt_tracking.update_payment_amount(payment, payment.paid_amount, current_user)
                    _logger.info(f"✅ อัปเดต Debt Tracking ID: {debt_tracking.id} "
                                f"Invoice: {invoice_name} Amount: {payment.paid_amount} "
                                f"โดย: {current_user.name}")
                else:
                    _logger.info(f"ℹ️ ไม่พบ Debt Tracking ที่ตรงกับ Invoice: {invoice_name} "
                                f"หรือสถานะไม่ใช่ done")

    def _clear_debt_tracking_payment(self):
        """
        เคลียร์ยอดชำระใน npd.debt.tracking เมื่อ payment ถูก reset to draft
        """
        for payment in self:
            if not payment.search_invoice_name:
                continue
            
            # แยกเลขใบแจ้งหนี้
            invoice_names = [name.strip() for name in payment.search_invoice_name.split(',')]
            
            _logger.info(f"🔄 Reset Payment: {payment.name} - เคลียร์ยอดใน Debt Tracking")
            
            for invoice_name in invoice_names:
                # หา account.move จากชื่อใบแจ้งหนี้
                invoice = self.env['account.move'].search([
                    ('name', '=', invoice_name)
                ], limit=1)
                
                if not invoice:
                    continue
                
                # หา npd.debt.tracking ที่มี payment_id ตรงกับ payment นี้
                debt_tracking = self.env['npd.debt.tracking'].search([
                    ('invoice_id', '=', invoice.id),
                    ('payment_id', '=', payment.id)
                ], limit=1)
                
                if debt_tracking:
                    debt_tracking.clear_payment_amount()
                    _logger.info(f"✅ เคลียร์ยอดชำระใน Debt Tracking ID: {debt_tracking.id}")
