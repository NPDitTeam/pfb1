# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLineLostItem(models.Model):
    _inherit = 'account.move.line'

    # x_discount_account = fields.Float(
    #     string='Discount (Line)',
    #     digits='Product Price',
    #     help='ส่วนลดต่อบรรทัดของเอกสาร ใช้ในการคำนวณยอดรวมส่วนลด (x_discount_amt_line)',
    #     default=0.0
    # )

    lost_item_amount = fields.Float(
        string='Lost Item Amount',
        compute='_compute_lost_item_amount',
        store=True,
        digits='Product Price',
        help='Calculated amount for lost items: (Quantity × Price) - Discount'
    )

    is_lost_item = fields.Boolean(
        string='Is Lost Item',
        compute='_compute_is_lost_item',
        store=True,
        help='Indicates if this line is a lost item with fixed discount'
    )

    @api.depends(
        'move_id.reason_code_id',
        'move_id.reason_code_id.name',
        'discount_method',
        'discount_amount'
    )
    def _compute_is_lost_item(self):
        """Check if this line is a 'Lost Item'"""
        for line in self:
            try:
                # ✅ ป้องกัน error ถ้า reason_code_id ไม่มี
                line.is_lost_item = (
                        hasattr(line.move_id, 'reason_code_id') and
                        line.move_id.reason_code_id
                )
            except AttributeError as e:
                _logger.warning(f"⚠️ reason_code_id not found: {e}")
                line.is_lost_item = False
            except Exception as e:
                _logger.error(f"❌ Error in _compute_is_lost_item: {e}")
                line.is_lost_item = False

    @api.depends(
        'quantity',
        'price_unit',
        'discount_amount',
        'discount_method',
        'is_lost_item'
    )
    def _compute_lost_item_amount(self):
        """Calculate: Quantity × Price Unit - Discount Amount"""
        for line in self:
            try:
                if line.is_lost_item:
                    # ✅ คำนวณส่วนลดตาม discount_method
                    discount = 0.0
                    total_price = line.quantity * line.price_unit

                    if line.discount_method == 'fix':
                        # ถ้าเป็น fix ใช้ยอดตามที่กรอก
                        discount = getattr(line, 'discount_amount', 0.0) or 0.0
                    elif line.discount_method == 'per':
                        # ถ้าเป็น per คำนวณเป็นจำนวนเงิน
                        discount_percent = getattr(line, 'discount_amount', 0.0) or 0.0
                        discount = total_price * (discount_percent / 100.0)

                    amount = total_price - discount
                    line.lost_item_amount = amount

                    _logger.info(
                        "💰 Lost Item Calculation: qty=%.2f × price=%.2f - discount(%.2f%s) = %.2f",
                        line.quantity, line.price_unit,
                        discount, ' (fix)' if line.discount_method == 'fix' else '%',
                        amount
                    )
                else:
                    line.lost_item_amount = 0.0
            except Exception as e:
                _logger.error(f"❌ Error in _compute_lost_item_amount: {e}")
                line.lost_item_amount = 0.0

    @api.onchange('quantity', 'price_unit', 'discount_amount', 'discount_method')
    def _onchange_lost_item_fields(self):
        """Trigger recompute when relevant fields change"""
        for line in self:
            try:
                if line.is_lost_item:
                    line._compute_lost_item_amount()
                    _logger.info("🔄 Lost Item Amount Updated: %.2f", line.lost_item_amount)

            except Exception as e:
                _logger.error(f"❌ Error in _onchange_lost_item_fields: {e}")