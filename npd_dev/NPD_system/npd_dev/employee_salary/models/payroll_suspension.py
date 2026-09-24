# -*- coding: utf-8 -*-
"""พักงาน — หักครึ่งหนึ่งของค่าจ้างรายวันตลอดช่วงที่ถูกพักงาน

ต่างจาก "ขาดงาน" ตรงที่พักงานเป็นคำสั่งของบริษัท ไม่ใช่ความผิดพลาดรายวัน
กติกาที่ใช้
  - นับทุกวันในช่วงที่สั่งพักงาน รวมวันหยุดและวันเสาร์อาทิตย์ด้วย
    (วันหยุดในช่วงพักงานก็ยังถือว่าถูกพักงาน ไม่ได้กลับมาทำงาน)
  - หักวันละ 50% ของค่าจ้างรายวัน (เท่ากับจ่าย 50%)
  - วันไหนที่อยู่ในช่วงพักงาน จะไม่ถูกคิดเป็นขาดงาน/สาย/ออกก่อนเวลา/ลา ซ้ำอีก
    เพราะไม่งั้นจะโดนหักซ้อนกันสองชั้น
  - ถ้าพบว่าวันนั้นยังมีการลงเวลาอยู่ (บริษัทสั่งพักงานแล้วแต่ยังมาตอกบัตร)
    ให้ถือว่าขาดงานตามคำสั่งพักงาน จ่าย 50% เท่าเดิม และติดธงไว้ให้ HR เห็น

วิธีรู้ว่า "ยังลงเวลาอยู่" ไม่ได้อ่านจากตารางลงเวลาในฐานนี้ เพราะคอลัมน์ user_id
ของตารางนั้นเป็นรหัสของระบบ PHP ไม่ใช่รหัสพนักงาน (ตรวจแล้วจับคู่ผิดคน)
จึงใช้การอนุมานจากผลที่ระบบคิดมาแล้วแทน: วันทำงานปกติที่ไม่ถูกตีเป็นขาดงาน
และไม่มีใบลา แปลว่าวันนั้นมีการลงเวลา ซึ่งเชื่อถือได้เท่ากับตัวเลขที่ใช้จ่ายเงินจริง
"""
import calendar
import datetime
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# จ่าย 50% ระหว่างพักงาน = หัก 50% ของค่าจ้างรายวัน
DEFAULT_SUSPENSION_DEDUCT_PERCENT = 50.0


class PayrollSalarySuspension(models.Model):
    _inherit = 'payroll.salary'

    suspension_start = fields.Date(
        string='วันที่เริ่มพักงาน',
        help='วันแรกที่ถูกสั่งพักงาน ปล่อยว่างไว้ถ้าไม่มีการพักงาน')
    suspension_end = fields.Date(
        string='วันที่สิ้นสุดพักงาน',
        help='วันสุดท้ายที่ถูกพักงาน (นับรวมวันนี้ด้วย)')
    suspension_deduct_percent = fields.Float(
        string='หักกี่ % ต่อวัน', default=DEFAULT_SUSPENSION_DEDUCT_PERCENT,
        help='ค่าเริ่มต้น 50 คือจ่ายครึ่งหนึ่งของค่าจ้างรายวัน '
             'ถ้าเคสไหนศาล/บริษัทสั่งเป็นอย่างอื่นค่อยแก้เฉพาะใบนั้น')
    suspension_reason = fields.Char(string='เหตุผลที่พักงาน')

    suspension_days = fields.Integer(
        string='จำนวนวันพักงาน (ในรอบนี้)', readonly=True,
        help='นับเฉพาะวันที่อยู่ในรอบเงินเดือนนี้ รวมวันหยุดด้วย')
    suspension_deduction = fields.Float(
        string='ยอดหักพักงาน', readonly=True)
    suspension_worked_days = fields.Integer(
        string='วันที่ยังลงเวลาทั้งที่ถูกพักงาน', readonly=True,
        help='ถูกพักงานแล้วแต่ยังมาลงเวลา ระบบยังถือว่าขาดงานตามคำสั่งพักงาน '
             'และจ่าย 50% เท่าเดิม ตัวเลขนี้มีไว้ให้ HR ตรวจสอบ')
    suspension_detail = fields.Text(string='รายละเอียดวันพักงาน', readonly=True)

    # ------------------------------------------------------------------
    @api.constrains('suspension_start', 'suspension_end')
    def _check_suspension_range(self):
        for rec in self:
            if rec.suspension_start and rec.suspension_end \
                    and rec.suspension_end < rec.suspension_start:
                raise ValidationError(_(
                    'วันที่สิ้นสุดพักงาน (%s) ต้องไม่ก่อนวันที่เริ่มพักงาน (%s)'
                ) % (rec.suspension_end, rec.suspension_start))
            if bool(rec.suspension_start) != bool(rec.suspension_end):
                raise ValidationError(_(
                    'พักงานต้องระบุทั้งวันที่เริ่มและวันที่สิ้นสุด'))

    @api.constrains('suspension_deduct_percent')
    def _check_suspension_percent(self):
        for rec in self:
            if not (0.0 <= (rec.suspension_deduct_percent or 0.0) <= 100.0):
                raise ValidationError(_(
                    'หักกี่ % ต่อวัน ต้องอยู่ระหว่าง 0 ถึง 100 (ใส่มา %s)'
                ) % rec.suspension_deduct_percent)

    # ------------------------------------------------------------------
    def _suspension_dates_in_cycle(self):
        """วันที่ถูกพักงานที่ตกอยู่ในรอบเงินเดือนนี้ (รวมวันหยุด) เรียงจากน้อยไปมาก"""
        self.ensure_one()
        if not (self.suspension_start and self.suspension_end):
            return []
        cycle_start, cycle_end = self._security_deposit_cycle_window()
        if not (cycle_start and cycle_end):
            return []
        first = max(self.suspension_start, cycle_start)
        last = min(self.suspension_end, cycle_end)
        if first > last:
            return []
        out, cur = [], first
        while cur <= last:
            out.append(cur)
            cur += datetime.timedelta(days=1)
        return out

    def _suspension_working_weekdays(self):
        """ชุดเลขวัน (0=จันทร์) ที่พนักงานคนนี้ต้องมาทำงานตามตารางกะ

        ใช้แยกว่าวันพักงานวันไหน "ควรจะมาทำงาน" เพื่อดูว่ายังแอบลงเวลาอยู่ไหม
        ไม่มีตารางกะให้ถือว่า จันทร์-เสาร์ เป็นวันทำงาน ตามค่าปกติของบริษัท
        """
        self.ensure_one()
        schedule = self.env['hr.work.schedule'].sudo().search(
            [('employee_id', '=', self.employee_id.id)], limit=1)
        if not schedule:
            return {0, 1, 2, 3, 4, 5}
        flags = [schedule.work_mon, schedule.work_tue, schedule.work_wed,
                 schedule.work_thu, schedule.work_fri, schedule.work_sat]
        return {idx for idx, is_work in enumerate(flags) if is_work}

    # ------------------------------------------------------------------
    def _apply_suspension(self, missed_days_log, late_log, early_log, leave_log,
                          late_checkin_minutes, early_checkout_minutes, missed_days,
                          deduction_absent, early_checkout_deduction,
                          deduction_absent_total, leave_deduction_total):
        """ตัดวันพักงานออกจากการคิดขาด/สาย/ลา แล้วคืนตัวเลขที่ปรับแล้ว

        คืน dict เพื่อให้ผู้เรียกหยิบไปใช้ได้ชัดเจนกว่าการคืน tuple ยาว ๆ
        ถ้าใบนี้ไม่มีการพักงาน จะคืนของเดิมทั้งหมดโดยไม่แตะอะไรเลย
        """
        self.ensure_one()
        result = {
            'missed_days_log': missed_days_log,
            'late_log': late_log,
            'early_log': early_log,
            'leave_log': leave_log,
            'late_checkin_minutes': late_checkin_minutes,
            'early_checkout_minutes': early_checkout_minutes,
            'missed_days': missed_days,
            'deduction_absent': deduction_absent,
            'early_checkout_deduction': early_checkout_deduction,
            'deduction_absent_total': deduction_absent_total,
            'leave_deduction_total': leave_deduction_total,
            'suspension_days': 0,
            'suspension_worked_days': 0,
            'suspension_deduction': 0.0,
            'suspension_lines': [],
            'suspension_detail': '',
        }
        susp_dates = self._suspension_dates_in_cycle()
        if not susp_dates:
            return result

        susp_str = {d.strftime('%Y-%m-%d') for d in susp_dates}
        salary_per_day = (self.base_salary or 0.0) / 30.0
        percent = self.suspension_deduct_percent
        if percent is None:
            percent = DEFAULT_SUSPENSION_DEDUCT_PERCENT
        per_day_deduct = salary_per_day * (percent / 100.0)

        def _date_of(item):
            return (item or {}).get('date')

        # --- ขาดงาน: วันที่ทับกับพักงาน ให้ถอดออก แล้วคืนเงินส่วนที่เคยหักเต็มวัน
        kept_missed = [d for d in (missed_days_log or []) if d not in susp_str]
        removed_missed = len(missed_days_log or []) - len(kept_missed)

        # --- ลา: ใบลาที่ตกในช่วงพักงาน ถือว่าพักงานมีผลเหนือกว่า
        kept_leave, removed_leave_amount = [], 0.0
        for item in (leave_log or []):
            if _date_of(item) in susp_str:
                removed_leave_amount += float(item.get('deduction') or 0.0)
            else:
                kept_leave.append(item)

        # --- สาย / ออกก่อนเวลา: วันพักงานไม่ควรถูกคิดอีก
        kept_late, removed_late_minutes = [], 0
        for item in (late_log or []):
            if _date_of(item) in susp_str:
                removed_late_minutes += int(item.get('minutes') or 0)
            else:
                kept_late.append(item)

        kept_early, removed_early_minutes = [], 0
        for item in (early_log or []):
            if _date_of(item) in susp_str:
                removed_early_minutes += int(item.get('minutes') or 0)
            else:
                kept_early.append(item)

        # เงินของ "ออกก่อนเวลา" มาจาก API เป็นก้อนเดียว จึงถอนตามสัดส่วนนาที
        early_removed_amount = 0.0
        if removed_early_minutes and (early_checkout_minutes or 0) > 0:
            early_removed_amount = (early_checkout_deduction or 0.0) * (
                removed_early_minutes / float(early_checkout_minutes))

        # --- วันที่ยังลงเวลาอยู่ทั้งที่ถูกพักงาน
        # วันทำงานตามกะ ที่ไม่ถูกตีเป็นขาดงาน และไม่มีใบลา = วันนั้นมีการลงเวลา
        work_weekdays = self._suspension_working_weekdays()
        holidays = set(self._official_holidays_for_cycle(tag='SUSPENSION'))
        leave_dates = {_date_of(i) for i in (leave_log or [])}
        absent_dates = set(missed_days_log or [])

        lines, detail_rows, worked_days = [], [], 0
        for day in susp_dates:
            key = day.strftime('%Y-%m-%d')
            is_workday = (day.weekday() in work_weekdays) and (key not in holidays)
            still_checked_in = (
                is_workday and key not in absent_dates and key not in leave_dates)
            if still_checked_in:
                worked_days += 1
            note = 'พักงาน'
            if still_checked_in:
                note = 'พักงาน (ยังลงเวลาอยู่ ถือว่าขาดงาน)'
            elif key in holidays:
                note = 'พักงาน (ตรงวันหยุด)'
            elif day.weekday() not in work_weekdays:
                note = 'พักงาน (ตรงวันหยุดประจำสัปดาห์)'
            lines.append({
                'date': day,
                'day_name': self.THAI_DOW_NAMES.get(day.weekday(), ''),
                'category': 'suspension',
                'description': note,
                'time_detail': 'ทั้งวัน',
                'minutes': 0.0,
                'amount': round(per_day_deduct, 2),
            })
            detail_rows.append('• %s (%s) %s' % (
                day.strftime('%d/%m/%Y'),
                self.THAI_DOW_NAMES.get(day.weekday(), ''), note))

        total_deduct = round(per_day_deduct * len(susp_dates), 2)

        result.update({
            'missed_days_log': kept_missed,
            'late_log': kept_late,
            'early_log': kept_early,
            'leave_log': kept_leave,
            'late_checkin_minutes': max((late_checkin_minutes or 0) - removed_late_minutes, 0),
            'early_checkout_minutes': max((early_checkout_minutes or 0) - removed_early_minutes, 0),
            'missed_days': max((missed_days or 0) - removed_missed, 0),
            'deduction_absent': max(
                (deduction_absent or 0.0) - removed_missed * salary_per_day, 0.0),
            'early_checkout_deduction': max(
                (early_checkout_deduction or 0.0) - early_removed_amount, 0.0),
            'deduction_absent_total': max(
                (deduction_absent_total or 0.0)
                - removed_missed * salary_per_day - early_removed_amount, 0.0),
            'leave_deduction_total': max(
                (leave_deduction_total or 0.0) - removed_leave_amount, 0.0),
            'suspension_days': len(susp_dates),
            'suspension_worked_days': worked_days,
            'suspension_deduction': total_deduct,
            'suspension_lines': lines,
            'suspension_detail': '\n'.join(
                ['หักวันละ %.2f บาท (%.0f%% ของค่าจ้างรายวัน %.2f บาท)'
                 % (per_day_deduct, percent, salary_per_day)] + detail_rows),
        })
        _logger.info(
            '[SUSPENSION] emp=%s ช่วง %s ถึง %s | ในรอบนี้ %d วัน | '
            'ยังลงเวลา %d วัน | หัก %.2f | ถอดขาดงานออก %d วัน ลา %.2f สาย %d นาที',
            self.employee_code, self.suspension_start, self.suspension_end,
            len(susp_dates), worked_days, total_deduct,
            removed_missed, removed_leave_amount, removed_late_minutes)
        return result
