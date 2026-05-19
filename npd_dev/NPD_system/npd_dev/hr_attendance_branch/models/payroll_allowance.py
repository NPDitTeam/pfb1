# -*- coding: utf-8 -*-
"""
Hook payroll.salary.income_allowance ให้ดึงจาก hr.manual.time.log อัตโนมัติ
- กรอง: employee_id ตรงกับ payroll.employee_id, state = 'อนุมัติ',
        reason_type = 'ค่าเบี้ยเลี้ยงออกนอกสถานที่'
- work_date อยู่ในรอบทำเงินเดือน (cutoff_start_day ของเดือนก่อน → cutoff_end_day ของเดือนนี้)
- รวม amount → set ที่ field income_allowance
"""
import calendar
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

APPROVED_STATE = 'อนุมัติ'

# Map: payroll.salary field → reason_type ใน hr.manual.time.log
INCOME_REASON_MAP = {
    'income_allowance': 'ค่าเบี้ยเลี้ยงออกนอกสถานที่',
    'income_food': 'ค่าอาหาร',
}

# Map: payroll.salary field → ชื่อ line ใน line_ids (ใช้ update line โดยตรง
# กรณี manual_override=True ทำให้ _populate_all_lines ไม่ rebuild line_ids)
INCOME_LINE_NAME_MAP = {
    'income_allowance': 'เบี้ยเลี้ยง',
    'income_food': 'ค่าอาหาร',
}


class PayrollSalaryAllowance(models.Model):
    _inherit = 'payroll.salary'

    def _get_payroll_period_range(self):
        """คืน (period_start, period_end) ตามรอบตัดเงินเดือน
        Convention (ตรงกับ actor content / OT / lateness ทั้งระบบ):
          period = cutoff_start ของเดือน "ก่อน" → cutoff_end ของเดือน "นี้"
        ตัวอย่าง: payroll เดือน 5, cutoff=25-24 → 25/04 → 24/05"""
        self.ensure_one()
        if not self.month or not self.year:
            return False, False
        try:
            month = int(self.month)
            year = int(self.year)
        except (TypeError, ValueError):
            return False, False
        cutoff_start = 25
        cutoff_end = 24
        if self.period_id:
            cutoff_start = self.period_id.cutoff_start_day or cutoff_start
            cutoff_end = self.period_id.cutoff_end_day or cutoff_end
        # period_end = วันที่ cutoff_end ของเดือนนี้ (month)
        last_day_curr = calendar.monthrange(year, month)[1]
        end = date(year, month, min(cutoff_end, last_day_curr))
        # period_start = วันที่ cutoff_start ของเดือนก่อน (month-1)
        prev = date(year, month, 1) - relativedelta(months=1)
        last_day_prev = calendar.monthrange(prev.year, prev.month)[1]
        start = date(prev.year, prev.month, min(cutoff_start, last_day_prev))
        return start, end

    def _refresh_manual_time_allowance(self):
        """ดึงผลรวม amount จาก hr.manual.time.log ที่อนุมัติแล้ว ในรอบนี้
        → set ที่ฟิลด์ของ payroll.salary ตาม INCOME_REASON_MAP (batch write ทีเดียว)"""
        ManualTimeLog = self.env['hr.manual.time.log'].sudo()
        for rec in self:
            if not rec.employee_id:
                continue
            start, end = rec._get_payroll_period_range()
            if not start or not end:
                continue
            ee_code = rec.employee_id.employee_code or ''
            if ee_code:
                base_domain = [
                    ('state', '=', APPROVED_STATE),
                    ('work_date', '>=', start),
                    ('work_date', '<=', end),
                    '|',
                    ('employee_id', '=', rec.employee_id.id),
                    ('user_id', '=', ee_code),
                ]
            else:
                base_domain = [
                    ('state', '=', APPROVED_STATE),
                    ('work_date', '>=', start),
                    ('work_date', '<=', end),
                    ('employee_id', '=', rec.employee_id.id),
                ]
            updates = {}
            for field_name, reason_type in INCOME_REASON_MAP.items():
                logs = ManualTimeLog.search(
                    base_domain + [('reason_type', '=', reason_type)]
                )
                total = sum(logs.mapped('amount'))
                current = getattr(rec, field_name, 0.0) or 0.0
                if abs(current - total) > 0.005:
                    updates[field_name] = total
            if updates:
                _logger.info(
                    "[ALLOWANCE_HOOK] Payroll %s/%s emp=%s period=%s→%s updates=%s",
                    rec.month, rec.year, rec.employee_id.employee_code,
                    start, end, updates,
                )
                rec.write(updates)
                # update line_ids โดยตรงสำหรับกรณี manual_override=True (line_ids ไม่ rebuild)
                for field_name, total in updates.items():
                    line_name = INCOME_LINE_NAME_MAP.get(field_name)
                    if not line_name:
                        continue
                    target_lines = rec.line_ids.filtered(lambda l: l.name == line_name)
                    if target_lines:
                        target_lines.write({'amount': total})

    def _populate_all_lines(self):
        if self.env.context.get('skip_manual_time_allowance_hook'):
            return super(PayrollSalaryAllowance, self)._populate_all_lines()
        self.with_context(skip_manual_time_allowance_hook=True)._refresh_manual_time_allowance()
        return super(PayrollSalaryAllowance, self)._populate_all_lines()

    @api.model_create_multi
    def create(self, vals_list):
        payrolls = super(PayrollSalaryAllowance, self).create(vals_list)
        if payrolls:
            payrolls.with_context(skip_manual_time_allowance_hook=True)._refresh_manual_time_allowance()
        return payrolls
