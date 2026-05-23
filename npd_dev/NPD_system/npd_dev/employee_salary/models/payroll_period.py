# -*- coding: utf-8 -*-

import calendar
import logging
import time
from datetime import date, datetime, timedelta
from psycopg2 import IntegrityError, OperationalError
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PayrollPeriod(models.Model):
    _name = "payroll.period"
    _description = "รอบทำเงินเดือน"
    _order = "year desc, month desc"

    _sql_constraints = [
        ('month_year_uniq', 'unique(month, year)',
         'ไม่สามารถสร้างรอบเงินเดือนซ้ำสำหรับเดือนและปีเดียวกันได้!')
    ]

    name = fields.Char(string="ชื่อรอบ", compute="_compute_name", store=True)
    month = fields.Integer(string="เดือน", required=True, default=lambda self: fields.Date.today().month)
    year = fields.Char(string="ปี", required=True, default=lambda self: str(fields.Date.today().year))
    cutoff_start_day = fields.Integer(string="วันเริ่มรอบ", default=25, required=True,
                                       help="วันที่เริ่มคิดเงินเดือน (ของเดือนก่อน)")
    cutoff_end_day = fields.Integer(string="วันสิ้นสุดรอบ", default=24, required=True,
                                     help="วันที่สิ้นสุดคิดเงินเดือน (ของเดือนนี้)")
    payment_date = fields.Date(string="วันที่จ่ายเงินเดือน")
    auto_run_date = fields.Date(string="วันที่รัน Auto",
                                 help="ระบบจะรันทำเงินเดือนอัตโนมัติในวันนี้")
    state = fields.Selection([
        ('draft', 'ร่าง'),
        ('processing', 'กำลังประมวลผล'),
        ('done', 'เสร็จสิ้น'),
        ('error', 'มีข้อผิดพลาด'),
    ], string="สถานะ", default='draft', required=True)

    test_employee_ids = fields.Many2many('employee.salary', string="พนักงานทดสอบ",
                                         help="เลือกพนักงานที่ต้องการทดสอบ ถ้าว่าง = รันทุกคนที่เปิด Auto")
    payroll_ids = fields.One2many('payroll.salary', 'period_id', string="รายการเงินเดือน")
    payroll_count = fields.Integer(string="จำนวนรายการ", compute="_compute_payroll_count")
    success_count = fields.Integer(string="สำเร็จ", readonly=True)
    error_count = fields.Integer(string="ผิดพลาด", readonly=True)
    log = fields.Text(string="บันทึก Log")

    @api.depends('month', 'year')
    def _compute_name(self):
        for rec in self:
            rec.name = "%02d/%s" % (rec.month or 0, rec.year or '')

    @api.depends('payroll_ids')
    def _compute_payroll_count(self):
        for rec in self:
            rec.payroll_count = len(rec.payroll_ids)

    @api.onchange('month', 'year', 'cutoff_end_day')
    def _onchange_set_auto_run_date(self):
        """ตั้งค่าเริ่มต้นวันที่อัตโนมัติเมื่อเลือกเดือน/ปี:
        - auto_run_date = วันที่ cutoff_end_day ของเดือนรอบ (รัน auto วันสิ้นสุด cycle)
        - payment_date  = วันที่ 28 ของเดือนรอบ (วันจ่ายเงินเดือน)
        """
        if self.month and self.year:
            try:
                import calendar
                m = int(self.month)
                y = int(self.year)
                last_day = calendar.monthrange(y, m)[1]
                if self.cutoff_end_day:
                    day = int(self.cutoff_end_day)
                    self.auto_run_date = date(y, m, min(day, last_day))
                self.payment_date = date(y, m, min(28, last_day))
            except (ValueError, TypeError):
                pass

    def action_run_auto_payroll(self):
        """รันทำเงินเดือน Auto สำหรับพนักงานที่เปิด auto_payroll"""
        self.ensure_one()
        if self.state not in ('draft', 'error'):
            raise UserError("สามารถรันได้เฉพาะรอบที่สถานะเป็น 'ร่าง' หรือ 'มีข้อผิดพลาด' เท่านั้น")

        # ไม่ล้าง log — เก็บประวัติการรันเดิมไว้ (จะถูก prepend ด้วย header timestamp ตอนจบ)
        self.write({'state': 'processing'})

        # คำนวณ "วันเริ่มรอบ" — เพื่อให้พนักงานที่ลาออกในรอบนี้ยังได้เงินเดือนรอบสุดท้าย
        try:
            m = int(self.month)
            y = int(self.year)
        except (TypeError, ValueError):
            m, y = fields.Date.today().month, fields.Date.today().year
        start_day = self.cutoff_start_day or 25
        if m == 1:
            prev_m, prev_y = 12, y - 1
        else:
            prev_m, prev_y = m - 1, y
        last_prev = calendar.monthrange(prev_y, prev_m)[1]
        cycle_start = date(prev_y, prev_m, min(start_day, last_prev))

        # ตัวกรอง: active ทุกคน + inactive ที่ resign_date อยู่ในรอบนี้ (>= วันเริ่มรอบ)
        # → พนักงานลาออกกลางรอบยังได้เงินเดือนรอบสุดท้าย
        #   แต่ถ้าลาออกไปก่อนรอบเริ่ม (resign_date < cycle_start) จะถูกข้าม
        def _eligible(emp):
            if emp.status == 'active':
                return True
            return bool(emp.resign_date and emp.resign_date >= cycle_start)

        # ถ้ามีพนักงานทดสอบ → ใช้เฉพาะคนที่เลือก, ถ้าว่าง → รันทุกคนที่เปิด Auto
        if self.test_employee_ids:
            employees = self.test_employee_ids.filtered(_eligible)
        else:
            candidates = self.env['employee.salary'].search([
                ('auto_payroll', '=', True),
                '|',
                ('status', '=', 'active'),
                '&',
                ('status', '=', 'inactive'),
                ('resign_date', '>=', cycle_start),
            ])
            employees = candidates.filtered(_eligible)

        if not employees:
            self.write({
                'state': 'error',
                'log': 'ไม่พบพนักงานที่เปิดทำเงินเดือน Auto',
            })
            return

        log_lines = []
        success_count = 0
        error_count = 0

        PayrollSalary = self.env['payroll.salary']
        MAX_RETRIES = 3  # retry สำหรับ concurrent / serialization errors
        for emp in employees:
            emp_label_first = emp.firstname or ''
            emp_label_code = emp.employee_code or ''

            # ✅ ตรวจสอบเงินเดือนก่อน — ถ้าไม่ระบุ ห้ามสร้าง payroll (กัน 0/None ทำให้ compute พัง)
            if not emp.salary or emp.salary <= 0:
                log_lines.append(
                    "[SKIP-NO-SALARY] %s (%s) - ไม่พบเงินเดือน กรุณาระบุเงินเดือนที่หน้าข้อมูลพนักงาน"
                    % (emp_label_first, emp_label_code))
                continue

            attempt = 0
            handled = False
            while attempt < MAX_RETRIES and not handled:
                attempt += 1
                try:
                    with self.env.cr.savepoint():
                        PayrollSalary.flush()
                        existing = PayrollSalary.search([
                            ('employee_id', '=', emp.id),
                            ('month', '=', self.month),
                            ('year', '=', self.year),
                        ], limit=1)

                        if existing:
                            log_lines.append("[SKIP] %s (%s) - มีรายการเงินเดือนอยู่แล้ว" % (
                                emp_label_first, emp_label_code))
                            success_count += 1
                            handled = True
                            continue

                        payroll_vals = {
                            'employee_id': emp.id,
                            'month': self.month,
                            'year': self.year,
                            'cutoff_day': self.cutoff_end_day,
                            'period_id': self.id,
                        }
                        if self.payment_date:
                            payroll_vals['payment_date'] = self.payment_date

                        PayrollSalary.create(payroll_vals)
                        success_count += 1
                        log_lines.append("[OK] %s (%s) - สร้างเงินเดือนสำเร็จ" % (
                            emp_label_first, emp_label_code))
                        handled = True

                except IntegrityError as e:
                    handled = True
                    if 'employee_month_year_uniq' in str(e):
                        # search รวม archived records (active=False) ด้วย — เพราะ DB constraint ก็ยัง enforce
                        existing = PayrollSalary.with_context(active_test=False).search([
                            ('employee_id', '=', emp.id),
                            ('month', '=', self.month),
                            ('year', '=', self.year),
                        ], limit=1)
                        if existing:
                            old_pid = existing.period_id.id
                            # บังคับเขียน period_id + active=True เสมอ
                            vals = {'period_id': self.id}
                            if not existing.active:
                                vals['active'] = True
                            existing.write(vals)
                            if old_pid != self.id:
                                log_lines.append(
                                    "[SKIP-DUP] %s (%s) - มีอยู่ในรอบอื่น (period_id=%s) → ย้ายมารอบนี้ + activate"
                                    % (emp_label_first, emp_label_code, old_pid))
                            else:
                                log_lines.append(
                                    "[SKIP-DUP] %s (%s) - มีรายการเงินเดือนอยู่แล้วในรอบนี้"
                                    % (emp_label_first, emp_label_code))
                        else:
                            # ดึงข้อมูลจาก DB ตรงๆ เพื่อ debug — บอก user ว่าใครเป็นเจ้าของ record นั้น
                            self.env.cr.execute(
                                """SELECT id, employee_id, period_id, active FROM payroll_salary
                                   WHERE month=%s AND year=%s
                                     AND employee_id IN (SELECT id FROM employee_salary
                                                         WHERE employee_code=%s)""",
                                (self.month, self.year, emp_label_code))
                            rows = self.env.cr.fetchall()
                            log_lines.append(
                                "[SKIP-DUP] %s (%s) - DB constraint fire แต่ search ไม่เจอ; raw rows=%s"
                                % (emp_label_first, emp_label_code, rows))
                        success_count += 1
                    else:
                        error_count += 1
                        log_lines.append("[ERROR] %s (%s) - DB constraint: %s" % (
                            emp_label_first, emp_label_code, str(e)))
                        _logger.exception("Auto payroll DB error for %s", emp_label_code)

                except OperationalError as e:
                    # serialization / concurrent update — retry
                    msg = str(e)
                    if 'could not serialize' in msg or 'deadlock detected' in msg:
                        if attempt < MAX_RETRIES:
                            time.sleep(0.1 * attempt)  # exponential-ish backoff
                            _logger.warning(
                                "[CONCURRENT] %s (%s) attempt %d/%d — retry...",
                                emp_label_first, emp_label_code, attempt, MAX_RETRIES,
                            )
                            continue  # retry
                        # ครบ retry → fail แต่บอก user ว่ารันใหม่ได้
                        handled = True
                        error_count += 1
                        log_lines.append(
                            "[ERROR-CONCURRENT] %s (%s) - concurrent update (รันปุ่ม Auto ใหม่อีกครั้งเพื่อสร้าง)"
                            % (emp_label_first, emp_label_code))
                        _logger.warning("Concurrent failure for %s after %d attempts", emp_label_code, MAX_RETRIES)
                    else:
                        handled = True
                        error_count += 1
                        log_lines.append("[ERROR] %s (%s) - DB error: %s" % (
                            emp_label_first, emp_label_code, msg))
                        _logger.exception("Auto payroll OperationalError for %s", emp_label_code)

                except Exception as e:
                    handled = True
                    error_count += 1
                    log_lines.append("[ERROR] %s (%s) - %s" % (
                        emp_label_first, emp_label_code, str(e)))
                    _logger.exception("Auto payroll error for %s", emp_label_code)

        final_state = 'done' if error_count == 0 else 'error'
        # ใช้เวลาตาม timezone ของ user (เช่น Asia/Bangkok = UTC+7) แทน UTC
        timestamp = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
        new_log = "[%s] รันทำเงินเดือน Auto: สำเร็จ %d, ผิดพลาด %d\n%s" % (
            timestamp, success_count, error_count, '\n'.join(log_lines))
        self.write({
            'state': final_state,
            'success_count': success_count,
            'error_count': error_count,
            'log': new_log,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ทำเงินเดือน Auto',
                'message': 'สำเร็จ %d รายการ, ผิดพลาด %d รายการ' % (success_count, error_count),
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': False,
            }
        }

    def action_generate_year(self):
        """สร้างรอบเงินเดือนทั้งปี (12 เดือน) จากรอบนี้"""
        self.ensure_one()
        year = self.year
        created = 0
        skipped = 0

        for m in range(1, 13):
            existing = self.search([('month', '=', m), ('year', '=', year)], limit=1)
            if existing:
                skipped += 1
                continue

            # คำนวณ auto_run_date = วันที่ cutoff_end_day ของเดือนรอบ (สิ้นสุด cycle)
            try:
                auto_run = date(int(year), m, self.cutoff_end_day)
            except ValueError:
                # กรณีเดือนไม่มีวันที่นั้น เช่น 31 ก.พ.
                import calendar
                last_day = calendar.monthrange(int(year), m)[1]
                auto_run = date(int(year), m, min(self.cutoff_end_day, last_day))

            # payment_date = วันที่ 28 ของเดือนรอบ (เดือนเดียวกัน)
            pay_date = date(int(year), m, 28)

            self.create({
                'month': m,
                'year': year,
                'cutoff_start_day': self.cutoff_start_day,
                'cutoff_end_day': self.cutoff_end_day,
                'auto_run_date': auto_run,
                'payment_date': pay_date,
                'state': 'draft',
            })
            created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'สร้างรอบทั้งปี %s' % year,
                'message': 'สร้างใหม่ %d รอบ, ข้าม %d รอบ (มีอยู่แล้ว)' % (created, skipped),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_reset_to_draft(self):
        """รีเซ็ตสถานะกลับเป็นร่าง"""
        self.ensure_one()
        self.write({'state': 'draft'})

    def _get_cycle_start(self):
        """วันเริ่มรอบ = cutoff_start_day ของเดือนก่อนหน้า (ตรงกับตัวกรองตอนสร้างเงินเดือน)"""
        try:
            m = int(self.month)
            y = int(self.year)
        except (TypeError, ValueError):
            today = fields.Date.today()
            m, y = today.month, today.year
        start_day = self.cutoff_start_day or 25
        if m == 1:
            prev_m, prev_y = 12, y - 1
        else:
            prev_m, prev_y = m - 1, y
        last_prev = calendar.monthrange(prev_y, prev_m)[1]
        return date(prev_y, prev_m, min(start_day, last_prev))

    def _is_eligible_employee(self, emp, cycle_start):
        """พนักงานเข้าเงื่อนไขรับเงินเดือนรอบนี้ไหม (ตรงกับ action_run_auto_payroll):
        - active = ได้เสมอ
        - inactive = ได้เฉพาะถ้ามีวันลาออก และลาออก >= วันเริ่มรอบ (ลาออกกลางรอบ → จ่ายรอบสุดท้าย)
        - inactive + ไม่มีวันลาออก / ลาออกก่อนรอบ → ไม่เข้าเงื่อนไข"""
        if emp.status == 'active':
            return True
        return bool(emp.resign_date and emp.resign_date >= cycle_start)

    def action_refresh_payrolls(self):
        """อัพเดตข้อมูลเงินเดือนทุกคนในรอบนี้ (คำนวณใหม่ OT/สาย/ขาด/ลา)"""
        self.ensure_one()
        if not self.payroll_ids:
            raise UserError("ยังไม่มีรายการเงินเดือนในรอบนี้ กรุณารันทำเงินเดือน Auto ก่อน")

        log_lines = []
        success_count = 0
        error_count = 0
        removed_count = 0

        # ถ้าตั้ง "พนักงานทดสอบ" ไว้ → refresh เฉพาะคนเหล่านั้น (ไว้ทดสอบทีละคน)
        # เคลียร์ field นี้เมื่อต้องการรันทุกคน
        payrolls_scope = self.payroll_ids
        if self.test_employee_ids:
            test_emp_ids = set(self.test_employee_ids.ids)
            payrolls_scope = self.payroll_ids.filtered(
                lambda p: p.employee_id.id in test_emp_ids)
            log_lines.append("[TEST MODE] refresh เฉพาะพนักงานทดสอบ %d คน" % len(payrolls_scope))

        # ลบรายการของพนักงานที่ "ไม่เข้าเงื่อนไขรอบนี้แล้ว" — เช่นเพิ่งแก้เป็นไม่ใช้งาน/ลาออกก่อนรอบ
        #   (ยกเว้นคนที่ติ๊ก manual_override เพื่อกันลบรายการที่ HR ปรับมือไว้)
        #   unlink จะ sync ลบไป PHP API ด้วย
        cycle_start = self._get_cycle_start()
        to_remove = payrolls_scope.filtered(
            lambda p: not p.manual_override
            and not self._is_eligible_employee(p.employee_id, cycle_start))
        payrolls_to_refresh = payrolls_scope - to_remove
        for p in to_remove:
            log_lines.append("[REMOVED] %s (%s) - ไม่เข้าเงื่อนไขรอบนี้ (ไม่ใช้งาน/ลาออกก่อนรอบ) → ลบออก" % (
                p.employee_id.firstname or '', p.employee_code or ''))
        if to_remove:
            removed_count = len(to_remove)
            to_remove.unlink()

        for payroll in payrolls_to_refresh:
            # อ่าน label เป็น local "ก่อน" savepoint — ถ้า body พัง transaction aborted
            # การอ่านฟิลด์ใน except จะพังซ้ำ (SQL fetch fail) ต้องเก็บไว้ก่อน
            emp_first = payroll.employee_id.firstname or ''
            emp_code = payroll.employee_code or ''

            if payroll.manual_override:
                log_lines.append("[SKIP] %s (%s) - ปรับแก้ด้วยมือ ข้ามการอัพเดต" % (
                    emp_first, emp_code))
                continue
            try:
                # savepoint per iteration — ถ้า payroll คนนึงพัง rollback ได้โดยไม่กระทบคนอื่น
                with self.env.cr.savepoint():
                    # _skip_payroll_write_side_effects: ดึง API + populate โดยข้าม side-effect
                    # ของทุก field write (auto populate + ยิง PHP + sync employee) → กัน write-storm
                    payroll_ctx = payroll.with_context(_skip_payroll_write_side_effects=True)
                    # recompute "เงินได้อื่นๆ" ใหม่ก่อนเพื่อรับรายการใน other.income ที่เพิ่งยืนยัน
                    payroll_ctx._compute_other_income_total()
                    payroll_ctx._parallel_fetch_all()
                    payroll_ctx._populate_all_lines()
                    # sync ครั้งเดียวตอนจบ (PHP + employee)
                    data = payroll._prepare_data_for_php()
                    payroll._send_data_to_php_api('update', data)
                    payroll._sync_latest_to_employee()
                    net_salary = payroll.net_salary
                success_count += 1
                log_lines.append("[UPDATED] %s (%s) - อัพเดตสำเร็จ | Net=%.2f" % (
                    emp_first, emp_code, net_salary))
            except Exception as e:
                error_count += 1
                log_lines.append("[ERROR] %s (%s) - %s" % (emp_first, emp_code, str(e)))
                _logger.error("Refresh payroll error for %s: %s", emp_code, e)

        # ใช้เวลาตาม timezone ของ user (เช่น Asia/Bangkok = UTC+7) แทน UTC
        timestamp = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
        new_log = "[%s] อัพเดตข้อมูล: สำเร็จ %d, ผิดพลาด %d, ลบออก %d\n%s" % (
            timestamp, success_count, error_count, removed_count, '\n'.join(log_lines))
        self.write({
            'log': new_log,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'อัพเดตข้อมูลเงินเดือน',
                'message': 'อัพเดต %d รายการ, ผิดพลาด %d, ลบออก %d รายการ' % (
                    success_count, error_count, removed_count),
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': False,
            }
        }

    @api.model
    def _cron_auto_payroll(self):
        """
        Cron job รันทุกวัน:
        1. ถ้าถึงรอบตัด (auto_run_date == วันนี้) และ state=draft → สร้างเงินเดือนใหม่
        2. รอบที่ state=done → อัพเดตข้อมูล (OT/สาย/ขาด/ลา) ทุกวัน เพื่อติดตามได้ตลอด
        """
        today = fields.Date.today()

        # 1) สร้างรอบใหม่ถ้าถึงวันตัดรอบ
        draft_periods = self.search([
            ('auto_run_date', '=', today),
            ('state', '=', 'draft'),
        ])
        for period in draft_periods:
            _logger.info("[CRON] สร้างเงินเดือนรอบ %s", period.name)
            try:
                period.action_run_auto_payroll()
            except Exception as e:
                _logger.error("[CRON] Error creating payroll for %s: %s", period.name, e)
                period.write({
                    'state': 'error',
                    'log': (period.log or '') + '\n[CRON ERROR] %s' % str(e),
                })

        # 1.5) สร้างรอบเดือนถัดไป "หลังจ่ายเงินเดือนรอบก่อนหน้า"
        #   trigger: มี period (state=done) ที่ payment_date < today (จ่ายแล้ว)
        #   และยังไม่มีรอบเดือนถัดไป → สร้างให้
        #   มอง 60 วันย้อนหลัง — ครอบ cron ที่อาจหลุดบางวัน + ไม่สร้าง future ไกลเกิน
        recent_paid = self.search([
            ('state', '=', 'done'),
            ('payment_date', '!=', False),
            ('payment_date', '<', today),
            ('payment_date', '>=', today - timedelta(days=60)),
        ])
        for paid in recent_paid:
            try:
                cur_month = int(paid.month)
                cur_year = int(paid.year)
            except (TypeError, ValueError):
                continue
            # เดือนถัดไป
            if cur_month == 12:
                next_month = 1
                next_year = str(cur_year + 1)
            else:
                next_month = cur_month + 1
                next_year = str(cur_year)

            existing_next = self.search([
                ('month', '=', next_month),
                ('year', '=', next_year),
            ], limit=1)
            if existing_next:
                continue  # มีรอบถัดไปแล้ว ข้าม

            cutoff_start = paid.cutoff_start_day or 25
            cutoff_end = paid.cutoff_end_day or 24

            try:
                auto_run = date(int(next_year), next_month, cutoff_end)
            except ValueError:
                last_day = calendar.monthrange(int(next_year), next_month)[1]
                auto_run = date(int(next_year), next_month, min(cutoff_end, last_day))

            # payment_date = วันที่ 28 ของเดือนรอบใหม่
            try:
                pay_date = date(int(next_year), next_month, 28)
            except ValueError:
                last_day = calendar.monthrange(int(next_year), next_month)[1]
                pay_date = date(int(next_year), next_month, min(28, last_day))

            self.create({
                'month': next_month,
                'year': next_year,
                'cutoff_start_day': cutoff_start,
                'cutoff_end_day': cutoff_end,
                'auto_run_date': auto_run,
                'payment_date': pay_date,
                'state': 'draft',
            })
            _logger.info(
                "[CRON] สร้างรอบใหม่ %02d/%s (หลังจ่ายเงินรอบ %s วันที่ %s)",
                next_month, next_year, paid.name, paid.payment_date)

        # 2) อัพเดตข้อมูลรอบที่เสร็จแล้ว (ติดตามทุกวัน)
        # อัพเดตเฉพาะรอบของเดือนปัจจุบัน หรือรอบที่ยังไม่ผ่านวันจ่ายเงิน
        active_periods = self.search([
            ('state', '=', 'done'),
            '|',
            ('payment_date', '>=', today),
            ('payment_date', '=', False),
        ])
        for period in active_periods:
            _logger.info("[CRON] อัพเดตข้อมูลรอบ %s", period.name)
            try:
                period.action_refresh_payrolls()
            except Exception as e:
                _logger.error("[CRON] Error refreshing payroll for %s: %s", period.name, e)

    def action_view_payrolls(self):
        """เปิดรายการเงินเดือนของรอบนี้"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'เงินเดือน - %s' % self.name,
            'res_model': 'payroll.salary',
            'view_mode': 'tree,form',
            'domain': [('period_id', '=', self.id)],
        }
