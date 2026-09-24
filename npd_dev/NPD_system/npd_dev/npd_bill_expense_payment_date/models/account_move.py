# -*- coding: utf-8 -*-
"""ย้ายวันที่ลงบัญชีของบิลผู้ขายไปตามวันที่รับชำระ

ดูเหตุผลและขอบเขตทั้งหมดใน __manifest__.py
"""
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, models
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

PARAM_MONTHS = "npd_bill_expense_payment_date.max_months_back"
DEFAULT_MONTHS = 2

# กัน recursion: write({'date': ...}) ด้านล่างไม่ควรวนกลับมาเรียกตัวเองอีก
SKIP_CTX = "npd_skip_expense_date_sync"


class AccountMove(models.Model):
    _inherit = "account.move"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _npd_max_months_back(self):
        """ระยะย้อนหลังสูงสุด (เดือน) ที่ยอมให้ย้ายวันที่ลงบัญชี"""
        raw = self.env["ir.config_parameter"].sudo().get_param(
            PARAM_MONTHS, DEFAULT_MONTHS)
        try:
            months = int(raw)
        except (TypeError, ValueError):
            _logger.warning(
                "%s มีค่าไม่ถูกต้อง (%r) ใช้ค่าเริ่มต้น %s เดือนแทน",
                PARAM_MONTHS, raw, DEFAULT_MONTHS)
            months = DEFAULT_MONTHS
        return max(months, 0)

    def _npd_payment_date(self):
        """วันที่รับชำระล่าสุดที่จับคู่กับบรรทัดเจ้าหนี้ของบิลใบนี้"""
        self.ensure_one()
        payable_lines = self.line_ids.filtered(
            lambda l: l.account_id.user_type_id.type == "payable")
        # บรรทัดเจ้าหนี้ของบิลอยู่ฝั่งเครดิต ใบรับชำระมาเดบิตล้าง
        # matched_debit_ids = partial ที่บรรทัดนี้เป็นฝั่งเครดิต
        dates = payable_lines.mapped(
            "matched_debit_ids.debit_move_id.move_id.date")
        return max(dates) if dates else False

    def _npd_date_change_blocked(self, new_date):
        """คืนข้อความเหตุผลถ้าเปลี่ยนวันที่ไม่ได้ คืน False ถ้าเปลี่ยนได้

        ตรวจเองล่วงหน้าแทนการดัก UserError เพราะ account.move.write() ตรวจ
        วันที่ล็อครอบสองหลังเขียนลงฐานข้อมูลไปแล้ว ถ้าไปดักตรงนั้นข้อมูลจะ
        ค้างครึ่ง ๆ กลาง ๆ
        """
        self.ensure_one()
        if self.restrict_mode_hash_table:
            return _("สมุดรายวันเปิดโหมดห้ามแก้ไข (strict mode)")

        lock_date = self.company_id._get_user_fiscal_lock_date()
        if lock_date and (self.date <= lock_date or new_date <= lock_date):
            return _("ติดวันที่ล็อคสิ้นงวด (%s)") % format_date(self.env, lock_date)

        tax_lock_date = self.company_id.tax_lock_date
        if (tax_lock_date and self._affect_tax_report()
                and (self.date <= tax_lock_date or new_date <= tax_lock_date)):
            return _("ติดวันที่ล็อคภาษี (%s)") % format_date(self.env, tax_lock_date)

        return False

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------
    def _npd_sync_expense_date_to_payment(self):
        """เขียนวันที่ลงบัญชีของบิลผู้ขายให้เท่ากับวันที่รับชำระ"""
        if self.env.context.get(SKIP_CTX):
            return

        months = self._npd_max_months_back()
        if not months:
            return

        for move in self:
            if move.move_type != "in_invoice" or move.state != "posted":
                continue
            # จ่ายไม่ครบไม่ย้าย เพราะ account_move.date มีค่าได้ค่าเดียว
            # ปันส่วนค่าใช้จ่ายข้ามเดือนตามงวดที่จ่ายไม่ได้
            if move.payment_state not in ("paid", "in_payment"):
                continue

            pay_date = move._npd_payment_date()
            if not pay_date or pay_date == move.date:
                continue

            oldest_allowed = pay_date - relativedelta(months=months)
            if move.date < oldest_allowed:
                move.message_post(body=_(
                    "ไม่ย้ายวันที่ลงบัญชีไปตามวันที่รับชำระ (%s) "
                    "เพราะวันที่ลงบัญชีเดิม (%s) ย้อนหลังเกิน %s เดือน"
                ) % (format_date(self.env, pay_date),
                     format_date(self.env, move.date), months))
                _logger.info(
                    "npd_bill_expense_payment_date: ข้าม %s (%s) "
                    "วันที่รับชำระ %s ย้อนหลังเกิน %s เดือน",
                    move.name, move.date, pay_date, months)
                continue

            blocked = move._npd_date_change_blocked(pay_date)
            if blocked:
                move.message_post(body=_(
                    "ไม่ย้ายวันที่ลงบัญชีไปเป็น %s: %s"
                ) % (format_date(self.env, pay_date), blocked))
                _logger.warning(
                    "npd_bill_expense_payment_date: ย้าย %s ไม่ได้ (%s)",
                    move.name, blocked)
                continue

            old_date = move.date
            # account_move_line.date        related store    -> ORM อัปเดตเอง
            # account_partial_reconcile.max_date stored compute -> ORM อัปเดตเอง
            move.with_context(**{SKIP_CTX: True}).write({"date": pay_date})
            # account_analytic_line.date ไม่ได้ผูกกับ move -> ต้องเขียนเอง
            analytic_lines = move.line_ids.analytic_line_ids
            if analytic_lines:
                analytic_lines.write({"date": pay_date})

            move.message_post(body=_(
                "ย้ายวันที่ลงบัญชีจาก %s เป็น %s ตามวันที่รับชำระ "
                "เพื่อให้ค่าใช้จ่ายออกรายงานตามเดือนที่จ่ายจริง"
            ) % (format_date(self.env, old_date),
                 format_date(self.env, pay_date)))
            _logger.info(
                "npd_bill_expense_payment_date: ย้าย %s จาก %s เป็น %s",
                move.name, old_date, pay_date)
