# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PaymentReprocessWizard(models.TransientModel):
    _name = 'payment.reprocess.wizard'
    _description = 'Wizard ค้นหาและดำเนินการรับชำระใหม่'

    # ===== ฟิลด์ค้นหา (ใช้ Char เพื่อไม่ให้ Odoo แปลง timezone) =====
    date_from = fields.Char(
        string='จากวันที่/เวลา',
        required=True,
        default=lambda self: (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),
    )
    date_to = fields.Char(
        string='ถึงวันที่/เวลา',
        required=True,
        default=lambda self: datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    )

    # ===== ผลลัพธ์ =====
    line_ids = fields.One2many(
        'payment.reprocess.wizard.line',
        'wizard_id',
        string='รายการ Payment ที่ถูกยกเลิก',
    )
    result_count = fields.Integer(
        string='จำนวนที่พบ',
        compute='_compute_result_count',
    )
    is_searched = fields.Boolean(
        string='ค้นหาแล้ว',
        default=False,
    )

    @api.depends('line_ids')
    def _compute_result_count(self):
        for rec in self:
            rec.result_count = len(rec.line_ids)

    def _parse_date_input(self, value):
        """
        แปลงวันที่จากหลายรูปแบบเป็น YYYY-MM-DD HH:MM:SS
        รองรับ:
          - DD/MM/YYYY HH:MM:SS  (เช่น 26/02/2026 17:15:00)
          - YYYY-MM-DD HH:MM:SS  (เช่น 2026-02-26 17:15:00)
          - DD/MM/YYYY HH:MM     (เช่น 26/02/2026 17:15)
          - YYYY-MM-DD HH:MM     (เช่น 2026-02-26 17:15)
          - MM/DD/YYYY HH:MM:SS  (fallback)
        """
        raw = (value or '').strip()
        if not raw:
            raise UserError(_("กรุณาระบุวันที่/เวลาให้ครบถ้วน"))

        # ลองหลายรูปแบบ
        formats = [
            '%Y-%m-%d %H:%M:%S',   # 2026-02-26 17:15:00
            '%Y-%m-%d %H:%M',      # 2026-02-26 17:15
            '%d/%m/%Y %H:%M:%S',   # 26/02/2026 17:15:00
            '%d/%m/%Y %H:%M',      # 26/02/2026 17:15
            '%m/%d/%Y %H:%M:%S',   # 02/26/2026 17:15:00 (fallback)
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(raw, fmt)
                # แปลงเป็น YYYY-MM-DD HH:MM:SS เสมอ
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue

        raise UserError(_(
            "รูปแบบวันที่ '%s' ไม่ถูกต้อง\n"
            "รองรับรูปแบบ:\n"
            "  - 2026-02-26 17:15:00\n"
            "  - 26/02/2026 17:15:00"
        ) % raw)

    def action_search(self):
        """ค้นหา Payment ที่ถูกยกเลิกในช่วงวันที่/เวลาที่กำหนด"""
        self.ensure_one()

        # ตรวจสอบและแปลงรูปแบบวันที่
        date_from_str = self._parse_date_input(self.date_from)
        date_to_str = self._parse_date_input(self.date_to)

        _logger.info("[Reprocess] ค้นหาช่วง: %s → %s" % (date_from_str, date_to_str))

        # ลบผลลัพธ์เก่า
        self.line_ids.unlink()

        # ค้นหา cancelled payments ตาม SQL query
        # ส่ง string ตรงๆ ไม่ผ่าน Odoo Datetime (ไม่มี timezone conversion)
        query = """
            SELECT
                ap.id AS payment_id,
                ap.name AS payment_name,
                am.name AS move_name,
                ap.payment_type,
                ap.amount,
                am.state,
                aj.name AS journal_name,
                TO_CHAR(
                    (am.write_date AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Bangkok',
                    'DD/MM/YYYY HH24:MI:SS'
                ) AS cancel_time_thai,
                rp.name AS partner_name
            FROM account_move am
            JOIN account_payment ap ON ap.move_id = am.id
            JOIN account_journal aj ON aj.id = am.journal_id
            LEFT JOIN res_partner rp ON rp.id = ap.partner_id
            WHERE am.state = 'cancel'
              AND am.write_date >= %s::timestamp
              AND am.write_date <= %s::timestamp
              AND am.write_date IN (
                  SELECT am2.write_date
                  FROM account_move am2
                  JOIN account_payment ap2 ON ap2.move_id = am2.id
                  WHERE am2.state = 'cancel'
                    AND am2.write_date >= %s::timestamp
                    AND am2.write_date <= %s::timestamp
                  GROUP BY am2.write_date
                  HAVING COUNT(*) > 2
              )
            ORDER BY am.write_date, ap.name
        """

        self.env.cr.execute(query, (
            date_from_str, date_to_str,
            date_from_str, date_to_str,
        ))
        results = self.env.cr.dictfetchall()

        _logger.info("[Reprocess Search] พบ %d รายการ" % len(results))

        # สร้าง wizard lines
        line_vals = []
        for row in results:
            line_vals.append((0, 0, {
                'wizard_id': self.id,
                'payment_id': row['payment_id'],
                'payment_name': row['payment_name'] or '',
                'move_name': row['move_name'] or '',
                'payment_type': row['payment_type'] or '',
                'amount': row['amount'] or 0.0,
                'journal_name': row['journal_name'] or '',
                'cancel_time_thai': row['cancel_time_thai'] or '',
                'partner_name': row['partner_name'] or '',
                'selected': True,
            }))

        self.write({
            'line_ids': line_vals,
            'is_searched': True,
        })

        # Return wizard เดิมเพื่อแสดงผลลัพธ์
        return {
            'name': _('ค้นหาและดำเนินการรับชำระใหม่'),
            'type': 'ir.actions.act_window',
            'res_model': 'payment.reprocess.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_reprocess_selected(self):
        """ดำเนินการรับชำระใหม่สำหรับรายการที่เลือก"""
        self.ensure_one()

        # เช็คสิทธิ์
        if not self.env.user.allow_payment_reprocess:
            raise UserError(_("คุณไม่มีสิทธิ์ดำเนินการรับชำระใหม่ กรุณาติดต่อผู้ดูแลระบบ"))

        selected_lines = self.line_ids.filtered(lambda l: l.selected)
        if not selected_lines:
            raise UserError(_("กรุณาเลือกอย่างน้อย 1 รายการที่ต้องการดำเนินการใหม่"))

        total = len(selected_lines)
        success = 0
        errors = []

        _logger.info("=" * 70)
        _logger.info("[Reprocess] เริ่มดำเนินการ %d รายการ" % total)
        _logger.info("=" * 70)

        for idx, line in enumerate(selected_lines, 1):
            payment = line.payment_id
            if not payment:
                errors.append("บรรทัดที่ %d: ไม่พบข้อมูล Payment" % idx)
                continue

            _logger.info(
                "[Reprocess] [%d/%d] กำลังดำเนินการ: %s" % (idx, total, payment.name)
            )

            try:
                self._reprocess_single_payment(payment)
                success += 1
                line.write({'status': 'success'})
                _logger.info("[Reprocess] ✅ สำเร็จ: %s" % payment.name)

            except Exception as e:
                error_msg = str(e)
                errors.append("%s: %s" % (payment.name, error_msg))
                line.write({'status': 'error', 'error_message': error_msg})
                _logger.error("[Reprocess] ❌ ล้มเหลว %s: %s" % (payment.name, error_msg))

        _logger.info("=" * 70)
        _logger.info(
            "[Reprocess] สรุป: สำเร็จ %d/%d | ล้มเหลว %d" % (
                success, total, len(errors)
            )
        )
        _logger.info("=" * 70)

        # Return wizard เดิมเพื่อแสดงผลลัพธ์ + สถานะ
        return {
            'name': _('ผลลัพธ์การดำเนินการ'),
            'type': 'ir.actions.act_window',
            'res_model': 'payment.reprocess.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _reprocess_single_payment(self, payment):
        """
        ดำเนินการรับชำระใหม่สำหรับ Payment เดียว:
        1. Reset to Draft
        2. Toggle Select off/on (refresh invoice IDs)
        3. Post ใหม่
        """
        move = payment.move_id

        # ========================================
        # ขั้นตอนที่ 1: Reset to Draft
        # ========================================
        if move.state == 'cancel':
            move.button_draft()
            _logger.info("  [Step 1] Move %s: cancel → draft" % move.name)
        elif move.state == 'posted':
            payment.with_context(
                skip_draft_permission_check=True
            ).action_draft()
            _logger.info("  [Step 1] Payment %s: posted → draft" % payment.name)
        elif move.state == 'draft':
            _logger.info("  [Step 1] อยู่ใน draft อยู่แล้ว")
        else:
            raise UserError(
                _("Payment %s อยู่ในสถานะ %s ไม่สามารถ reprocess ได้")
                % (payment.name, move.state)
            )

        # ========================================
        # ขั้นตอนที่ 2: Toggle Select off/on
        # (refresh invoice IDs + amount_due)
        # ========================================
        for invoice_line in payment.invoice_ids:
            if not invoice_line.invoice_id:
                continue

            invoice = invoice_line.invoice_id

            # Refresh data จาก database
            invoice.invalidate_cache()
            invoice.refresh()

            new_amount_due = abs(invoice.amount_residual)

            _logger.info(
                "  [Step 2] Invoice %s: amount_due %s → %s" % (
                    invoice.name,
                    invoice_line.amount_due,
                    new_amount_due,
                )
            )

            # Toggle off
            invoice_line.write({
                'paid': False,
                'paid_total': 0,
            })

            # Toggle on (พร้อม amount_due ล่าสุด)
            invoice_line.write({
                'paid': True,
                'amount_due': new_amount_due,
                'paid_total': new_amount_due,
            })

        # Recalculate payment amount
        total_paid = sum(
            inv.paid_total for inv in payment.invoice_ids if inv.paid
        )
        wht = sum(line.tax_amount or 0 for line in payment.wt_cert_ids)
        payment.write({'amount': total_paid - wht})

        _logger.info("  [Step 2] Recalculated amount = %s" % payment.amount)

        # ========================================
        # ขั้นตอนที่ 3: Post ใหม่
        # ========================================
        payment.action_post()
        _logger.info("  [Step 3] ✅ Posted สำเร็จ: %s" % payment.name)

    def action_select_all(self):
        """เลือกทั้งหมด"""
        self.ensure_one()
        self.line_ids.write({'selected': True})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payment.reprocess.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_deselect_all(self):
        """ยกเลิกเลือกทั้งหมด"""
        self.ensure_one()
        self.line_ids.write({'selected': False})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payment.reprocess.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class PaymentReprocessWizardLine(models.TransientModel):
    _name = 'payment.reprocess.wizard.line'
    _description = 'รายการ Payment ที่ถูกยกเลิก'

    wizard_id = fields.Many2one(
        'payment.reprocess.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
    )
    payment_name = fields.Char(string='เลขที่ใบรับชำระ')
    move_name = fields.Char(string='เลขที่ Journal Entry')
    payment_type = fields.Char(string='ประเภท')
    amount = fields.Float(string='ยอดชำระ')
    journal_name = fields.Char(string='สมุดรายวัน')
    cancel_time_thai = fields.Char(string='วัน/เวลายกเลิก (ไทย)')
    partner_name = fields.Char(string='ลูกค้า/ผู้จำหน่าย')
    selected = fields.Boolean(string='เลือก', default=True)
    status = fields.Selection([
        ('pending', 'รอดำเนินการ'),
        ('success', 'สำเร็จ'),
        ('error', 'ล้มเหลว'),
    ], string='สถานะ', default='pending')
    error_message = fields.Char(string='รายละเอียดข้อผิดพลาด')
