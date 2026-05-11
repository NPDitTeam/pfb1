# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _is_from_sale_order(self):
        """Check if invoice origin starts with SO (Sales Order)"""
        if self.invoice_origin:
            return self.invoice_origin.startswith('SO')
        return False

    def _is_from_purchase_order(self):
        """Check if invoice origin starts with PO (Purchase Order)"""
        if self.invoice_origin:
            return self.invoice_origin.startswith('PO')
        return False

    def _is_vendor_bill(self):
        """Check if this is a vendor bill (purchase-related)"""
        return self.move_type in ('in_invoice', 'in_refund')

    @api.onchange('discount_method')
    def _onchange_discount_method_restriction(self):
        """
        Restrict discount method to 'per' (Percentage) only on account.move.
        Only applies to invoices from Sales Orders (SO), skips Purchase Orders (PO) and Vendor Bills.
        """
        _logger.info('=== NPD: onchange discount_method on account.move, value=%s, origin=%s, move_type=%s ===',
                     self.discount_method, self.invoice_origin, self.move_type)

        # Skip if Vendor Bill (in_invoice, in_refund)
        if self._is_vendor_bill():
            _logger.info('=== NPD: Skipping restriction - Vendor Bill ===')
            return

        # Skip if from Purchase Order (PO)
        if self._is_from_purchase_order():
            _logger.info('=== NPD: Skipping restriction - Invoice from PO ===')
            return

        # Apply restriction only for Sales Orders (SO)
        if self._is_from_sale_order():
            if self.discount_method == 'fix':
                self.discount_method = 'per'
                return {
                    'warning': {
                        'title': _('ข้อจำกัดวิธีการคิดส่วนลด'),
                        'message': _(
                            'ไม่สามารถเลือก "Fixed" ได้!\n'
                            'ระบบอนุญาตให้ใช้เฉพาะ "Percentage" เท่านั้น\n'
                            '(ใช้กับ Invoice จาก Sales Order เท่านั้น)\n'
                        ),
                    }
                }

    @api.constrains('discount_method')
    def _check_discount_method_restriction(self):
        for record in self:
            # Skip if Vendor Bill (in_invoice, in_refund)
            if record._is_vendor_bill():
                _logger.info('=== NPD: Skipping constrains - Vendor Bill ===')
                continue

            # Skip if from Purchase Order (PO)
            if record._is_from_purchase_order():
                _logger.info('=== NPD: Skipping constrains - Invoice from PO ===')
                continue

            # Apply restriction only for Sales Orders (SO)
            if record._is_from_sale_order():
                if record.discount_method == 'fix':
                    raise ValidationError(_(
                        'ไม่สามารถบันทึกด้วย Discount Method = "Fixed" ได้!\n'
                        'กรุณาใช้ "Percentage" เท่านั้น\n'
                        '(ใช้กับ Invoice จาก Sales Order เท่านั้น)\n'
                    ))


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _is_from_sale_order(self):
        """Check if parent invoice origin starts with SO (Sales Order)"""
        if self.move_id and self.move_id.invoice_origin:
            return self.move_id.invoice_origin.startswith('SO')
        return False

    def _is_from_purchase_order(self):
        """Check if parent invoice origin starts with PO (Purchase Order)"""
        if self.move_id and self.move_id.invoice_origin:
            return self.move_id.invoice_origin.startswith('PO')
        return False

    def _is_vendor_bill(self):
        """Check if parent is a vendor bill (purchase-related)"""
        if self.move_id:
            return self.move_id.move_type in ('in_invoice', 'in_refund')
        return False

    @api.onchange('discount_method')
    def _onchange_discount_method_line_restriction(self):
        """
        Restrict discount method to 'per' (Percentage) only on account.move.line.
        Only applies to invoices from Sales Orders (SO), skips Purchase Orders (PO) and Vendor Bills.
        """
        _logger.info('=== NPD: onchange discount_method on account.move.line, value=%s, origin=%s, move_type=%s ===',
                     self.discount_method,
                     self.move_id.invoice_origin if self.move_id else None,
                     self.move_id.move_type if self.move_id else None)

        # Skip if Vendor Bill (in_invoice, in_refund)
        if self._is_vendor_bill():
            _logger.info('=== NPD: Skipping line restriction - Vendor Bill ===')
            return

        # Skip if from Purchase Order (PO)
        if self._is_from_purchase_order():
            _logger.info('=== NPD: Skipping line restriction - Invoice from PO ===')
            return

        # Apply restriction only for Sales Orders (SO)
        if self._is_from_sale_order():
            if self.discount_method == 'fix':
                self.discount_method = 'per'
                return {
                    'warning': {
                        'title': _('ข้อจำกัดวิธีการคิดส่วนลด (Invoice Line)'),
                        'message': _(
                            'ไม่สามารถเลือก "Fixed" ได้!\n'
                            'ระบบอนุญาตให้ใช้เฉพาะ "Percentage" เท่านั้น\n'
                            '(ใช้กับ Invoice จาก Sales Order เท่านั้น)\n'
                        ),
                    }
                }

    @api.constrains('discount_method')
    def _check_discount_method_line_restriction(self):
        for record in self:
            # Skip if Vendor Bill (in_invoice, in_refund)
            if record._is_vendor_bill():
                _logger.info('=== NPD: Skipping line constrains - Vendor Bill ===')
                continue

            # Skip if from Purchase Order (PO)
            if record._is_from_purchase_order():
                _logger.info('=== NPD: Skipping line constrains - Invoice from PO ===')
                continue

            # Apply restriction only for Sales Orders (SO)
            if record._is_from_sale_order():
                if record.discount_method == 'fix':
                    raise ValidationError(_(
                        'ไม่สามารถบันทึกรายการด้วย Discount Method = "Fixed" ได้!\n'
                        'Product: %s\n'
                        'กรุณาใช้ "Percentage" เท่านั้น\n'
                        '(ใช้กับ Invoice จาก Sales Order เท่านั้น)\n'
                    ) % (record.product_id.name or record.name or '-'))
