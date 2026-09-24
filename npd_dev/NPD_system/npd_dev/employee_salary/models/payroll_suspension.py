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

    # ช่องพวกนี้เป็นแค่ที่แสดงผล คนกรอกจริงอยู่ที่แท็บ "พักงาน" ของพนักงาน
    # ตั้งใจไม่ให้กรอกที่ใบเงินเดือน เพราะถ้ากรอกได้สองที่จะขัดกันเอง
    # และข้อมูลที่ผูกกับใบจะหายทุกครั้งที่ลบใบแล้วสร้างใหม่
    suspension_start = fields.Date(string='วันที่เริ่มพักงาน', readonly=True)
    suspension_end = fields.Date(string='วันที่สิ้นสุดพักงาน', readonly=True)
    suspension_reason = fields.Char(string='เหตุผลที่พักงาน', readonly=True)

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
    def _suspension_dates_in_cycle(self):
        """วันที่ถูกพักงานที่ตกอยู่ในรอบเงินเดือนนี้ (รวมวันหยุด)

        อ่านจากคำสั่งพักงานของพนักงาน รองรับหลายคำสั่งในรอบเดียวกัน
        และรองรับคำสั่งที่คร่อมสองรอบ โดยตัดเอาเฉพาะส่วนที่อยู่ในรอบนี้
        คืน dict {วันที่: % ที่ต้องหัก} เพื่อให้แต่ละคำสั่งใช้ % ของตัวเองได้
        """
        self.ensure_one()
        cycle_start, cycle_end = self._security_deposit_cycle_window()
        if not (cycle_start and cycle_end and self.employee_id):
            return {}
        orders = self.env['employee.suspension'].suspensions_in_range(
            self.employee_id, cycle_start, cycle_end)
        out = {}
        for order in orders:
            first = max(order.date_start, cycle_start)
            last = min(order.date_end, cycle_end)
            cur = first
            while cur <= last:
                out[cur] = order.deduct_percent
                cur += datetime.timedelta(days=1)
        return dict(sorted(out.items()))

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

        # susp_dates = {วันที่: % ที่ต้องหักของวันนั้น} แต่ละคำสั่งใช้ % ของตัวเอง
        susp_str = {d.strftime('%Y-%m-%d') for d in susp_dates}
        salary_per_day = (self.base_salary or 0.0) / 30.0

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
        total_deduct = 0.0
        for day, percent in susp_dates.items():
            per_day_deduct = salary_per_day * ((percent or 0.0) / 100.0)
            total_deduct += per_day_deduct
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
            detail_rows.append('• %s (%s) %s — หัก %.2f บาท (%.0f%%)' % (
                day.strftime('%d/%m/%Y'),
                self.THAI_DOW_NAMES.get(day.weekday(), ''), note,
                per_day_deduct, percent or 0.0))

        total_deduct = round(total_deduct, 2)
        # เก็บช่วงกับเหตุผลไว้แสดงบนใบ (คนกรอกจริงอยู่ที่แท็บพักงานของพนักงาน)
        days_sorted = sorted(susp_dates)
        orders = self.env['employee.suspension'].suspensions_in_range(
            self.employee_id, days_sorted[0], days_sorted[-1])
        self.suspension_start = days_sorted[0]
        self.suspension_end = days_sorted[-1]
        self.suspension_reason = ' / '.join(
            o.reason for o in orders if o.reason) or ''

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
                ['ค่าจ้างรายวัน %.2f บาท' % salary_per_day] + detail_rows),
        })
        _logger.info(
            '[SUSPENSION] emp=%s ช่วง %s ถึง %s | ในรอบนี้ %d วัน | '
            'ยังลงเวลา %d วัน | หัก %.2f | ถอดขาดงานออก %d วัน ลา %.2f สาย %d นาที',
            self.employee_code, days_sorted[0], days_sorted[-1],
            len(susp_dates), worked_days, total_deduct,
            removed_missed, removed_leave_amount, removed_late_minutes)
        return result
