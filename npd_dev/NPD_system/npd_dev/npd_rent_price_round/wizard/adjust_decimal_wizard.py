# -*- coding: utf-8 -*-
"""
Wizard: แก้ไขยอดทศนิยม (Decimal Adjustment)

ใช้สำหรับ ใบแจ้งหนี้ / ใบลดหนี้ / Debit Note ที่ user คำนวณยอดเป้าหมาย
จากเงื่อนไขภายในแล้วยอดที่ระบบคำนวณได้ห่างจาก target (เช่น drift 0.01
จาก 2dp rounding หรือ user ต้องการปรับให้ตรงเลขอื่น) → wizard ให้ user
ปรับยอดทศนิยมเพื่อให้ตรงเป๊ะ

รองรับ move types:
    - out_invoice (ใบแจ้งหนี้)
    - in_invoice (Vendor Bill)
    - out_refund (ใบลดหนี้)
    - in_refund (Vendor Refund)
    - Debit Note (อยู่ในกลุ่ม out_invoice/in_invoice ที่มี debit_origin_id)

Workflow:
    1. กดปุ่ม "แก้ไขยอดทศนิยม" บนฟอร์มเอกสาร
    2. Popup แสดงยอดรวมปัจจุบัน + ให้เลือกปรับ +/- ทศนิยม
    3. กด "ปรับยอด" → set move.target_amount_total → trigger
       _npd_force_round_sql → ปรับ tax line + receivable + amount_total
       + amount_residual
    4. Form auto-refresh เห็นยอดใหม่
"""

from odoo import api, fields, models
from odoo.exceptions import UserError


# Selection presets — ค่าที่ใช้บ่อย
PRESET_MAX_ABS = 0.05  # บาท (สำหรับ Selection options ±0.01-0.05)

# Custom field — ทศนิยมเท่านั้น (< 1.00 บาท) ไม่จำกัดในช่วงนั้น
# user ใส่ได้ตั้งแต่ ±0.01 ถึง ±0.99 (เป็น "ยอดทศนิยม" — ไม่ใช่บาทเต็ม)
CUSTOM_LIMIT = 1.0  # strict less than (ไม่อนุญาต ±1.00 ขึ้นไป)


class NpdAdjustDecimalWizard(models.TransientModel):
    _name = 'npd.adjust.decimal.wizard'
    _description = 'แก้ไขยอดทศนิยม (Invoice / Credit Note / Debit Note)'

    move_id = fields.Many2one(
        'account.move',
        string='เอกสาร',
        required=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        related='move_id.currency_id',
        readonly=True,
    )

    current_total = fields.Monetary(
        string='ยอดรวมปัจจุบัน',
        related='move_id.amount_total',
        currency_field='currency_id',
        readonly=True,
    )

    adjustment_choice = fields.Selection([
        ('plus_001', '+0.01'),
        ('plus_002', '+0.02'),
        ('plus_005', '+0.05'),
        ('minus_001', '−0.01'),
        ('minus_002', '−0.02'),
        ('minus_005', '−0.05'),
        ('custom', 'กำหนดเอง'),
        ('reset', 'รีเซ็ตยอดเดิม (ลบ adjustment)'),
    ], string='ปรับเพิ่ม/ลด',
       default='plus_001',
       required=True,
       help='Preset: ±0.01 ถึง ±0.05 / กำหนดเอง: ค่าทศนิยมใดๆ '
            '(< 1.00 บาท) / รีเซ็ต: ลบ adjustment')

    custom_adjustment = fields.Float(
        string='ค่าปรับ (กำหนดเอง)',
        digits=(16, 2),
        help='ใส่ค่าทศนิยมที่ต้องการ ต้องน้อยกว่า 1.00 บาท เท่านั้น '
             '(เช่น 0.03, -0.27, 0.95, -0.99) — ค่าตั้งแต่ ±1.00 '
             'ขึ้นไปจะถูกปฏิเสธ เพราะ wizard นี้ใช้สำหรับปรับเฉพาะ '
             'ทศนิยมเท่านั้น',
    )

    new_total = fields.Monetary(
        string='ยอดรวมหลังปรับ',
        compute='_compute_new_total',
        currency_field='currency_id',
    )

    delta = fields.Float(
        string='ค่าปรับสุทธิ',
        compute='_compute_new_total',
        digits=(16, 2),
    )

    # =========================================================
    # Mapping & Compute
    # =========================================================
    _CHOICE_MAP = {
        'plus_001': 0.01, 'plus_002': 0.02, 'plus_005': 0.05,
        'minus_001': -0.01, 'minus_002': -0.02, 'minus_005': -0.05,
    }

    @api.depends('current_total', 'adjustment_choice', 'custom_adjustment')
    def _compute_new_total(self):
        for w in self:
            if w.adjustment_choice == 'reset':
                # reset = ลบ target → ยอดจะกลับเป็นค่าธรรมชาติของ Method A
                w.delta = 0.0
                w.new_total = 0.0
            elif w.adjustment_choice == 'custom':
                # จำกัด custom ไว้ที่ |value| ≤ 0.05
                v = w.custom_adjustment or 0.0
                # clamp to range (display preview only, validate on apply)
                w.delta = v
                w.new_total = w.current_total + v
            else:
                w.delta = self._CHOICE_MAP.get(w.adjustment_choice, 0.0)
                w.new_total = w.current_total + w.delta

    # =========================================================
    # Validation (onchange)
    # =========================================================
    @api.onchange('custom_adjustment', 'adjustment_choice')
    def _onchange_validate_custom(self):
        """แจ้งเตือนถ้า custom_adjustment ≥ 1 บาท (ทศนิยมเท่านั้น)"""
        if self.adjustment_choice != 'custom':
            return
        v = self.custom_adjustment or 0.0
        if abs(v) >= CUSTOM_LIMIT:
            return {
                'warning': {
                    'title': 'ค่าเกินขีดจำกัด',
                    'message': (
                        'wizard นี้รองรับเฉพาะการปรับทศนิยมเท่านั้น '
                        '(ต้องน้อยกว่า ±%.2f บาท)\n'
                        'ค่าที่ใส่ (%.2f) เป็นบาทเต็มขึ้นไป — '
                        'กรุณาใส่ค่าทศนิยม เช่น 0.27, -0.95'
                        % (CUSTOM_LIMIT, v)
                    )
                }
            }

    # =========================================================
    # Action
    # =========================================================
    # Fields ที่ต้อง invalidate หลัง update เพื่อให้ form อ่านค่าใหม่
    _FIELDS_TO_REFRESH_MOVE = [
        'amount_untaxed', 'amount_tax', 'amount_total', 'amount_residual',
        'amount_price_subtotal_without_discount', 'discount_amt_line',
        'amount_price_total_full', 'target_amount_total',
    ]
    _FIELDS_TO_REFRESH_LINE = [
        'debit', 'credit', 'balance', 'amount_currency',
        'amount_residual', 'amount_residual_currency',
        'price_subtotal', 'price_total',
    ]

    def _refresh_move_cache(self, move):
        """Invalidate ORM cache ของฟิลด์ที่ถูกแก้ใน _npd_force_round_sql
        เพื่อให้ form อ่านค่าใหม่จาก DB หลัง wizard ปิด"""
        existing_move_fields = [
            f for f in self._FIELDS_TO_REFRESH_MOVE
            if f in move._fields
        ]
        if existing_move_fields:
            move.invalidate_cache(existing_move_fields, [move.id])
        existing_line_fields = [
            f for f in self._FIELDS_TO_REFRESH_LINE
            if f in self.env['account.move.line']._fields
        ]
        if existing_line_fields:
            move.line_ids.invalidate_cache(existing_line_fields)

    def _flush_and_refresh(self, move):
        """บังคับ flush ORM writes ลง DB + invalidate cache + return action
        ที่บังคับ parent form re-read (ไม่ต้อง full page reload)"""
        # Flush ORM cache → DB
        self.env['account.move'].flush()
        self.env['account.move.line'].flush()
        # Invalidate cache → form's next read goes to DB
        self._refresh_move_cache(move)
        # Return action with infos.reload hint → Odoo 14 action manager
        # จะ re-read parent record หลัง wizard ปิด
        return {
            'type': 'ir.actions.act_window_close',
            'infos': {'reload': True},
        }

    def action_apply(self):
        self.ensure_one()
        move = self.move_id
        if not move:
            raise UserError('ไม่พบเอกสารที่ต้องการปรับยอด')

        # === Reset path: ล้าง target_amount_total ===
        if self.adjustment_choice == 'reset':
            move.target_amount_total = 0.0
            return self._flush_and_refresh(move)

        # === Adjustment path ===
        delta = self.delta
        if abs(delta) < 0.005:
            raise UserError('ค่าปรับต้องไม่เป็น 0 — เลือกตัวเลือกอื่น')

        # Validate ตาม source ของ delta:
        # - Selection presets: limit ±0.05 (preset values are all ≤ 0.05)
        # - Custom field: limit < 1.00 (decimal only, no whole-baht adjust)
        if self.adjustment_choice == 'custom':
            if abs(delta) >= CUSTOM_LIMIT:
                raise UserError(
                    'ช่องกำหนดเองรองรับเฉพาะค่าทศนิยม (น้อยกว่า ±%.2f บาท) '
                    'ค่าที่ใส่ (%.2f) เป็นบาทเต็มขึ้นไป — ไม่อนุญาต'
                    % (CUSTOM_LIMIT, delta)
                )
        else:
            if abs(delta) > PRESET_MAX_ABS:
                raise UserError(
                    'Preset value เกินขีดจำกัด ±%.2f บาท (delta = %.2f)'
                    % (PRESET_MAX_ABS, delta)
                )

        new_target = round(move.amount_total + delta, 2)
        if new_target <= 0:
            raise UserError(
                'ยอดหลังปรับ (%.2f) ต้องเป็นบวก' % new_target
            )

        # set target → trigger _npd_force_round_sql ผ่าน write hook
        move.target_amount_total = new_target

        return self._flush_and_refresh(move)
