# -*- coding: utf-8 -*-

import logging
from datetime import date, datetime
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

        self.write({'state': 'processing', 'log': ''})

        # ถ้ามีพนักงานทดสอบ → ใช้เฉพาะคนที่เลือก, ถ้าว่าง → รันทุกคนที่เปิด Auto
        if self.test_employee_ids:
            employees = self.test_employee_ids.filtered(lambda e: e.status == 'active')
        else:
            employees = self.env['employee.salary'].search([
                ('auto_payroll', '=', True),
                ('status', '=', 'active'),
            ])

        if not employees:
            self.write({
                'state': 'error',
                'log': 'ไม่พบพนักงานที่เปิดทำเงินเดือน Auto',
            })
            return

        log_lines = []
        success_count = 0
        error_count = 0

        for emp in employees:
            try:
                # ตรวจสอบว่ามี payroll record อยู่แล้วหรือไม่
                existing = self.env['payroll.salary'].search([
                    ('employee_id', '=', emp.id),
                    ('month', '=', self.month),
                    ('year', '=', self.year),
                ], limit=1)

                if existing:
                    log_lines.append("[SKIP] %s (%s) - มีรายการเงินเดือนอยู่แล้ว" % (
                        emp.firstname, emp.employee_code))
                    success_count += 1
                    continue

                # สร้าง payroll record ใหม่
                payroll_vals = {
                    'employee_id': emp.id,
                    'month': self.month,
                    'year': self.year,
                    'cutoff_day': self.cutoff_end_day,
                    'period_id': self.id,
                }
                if self.payment_date:
                    payroll_vals['payment_date'] = self.payment_date

                self.env['payroll.salary'].create(payroll_vals)
                success_count += 1
                log_lines.append("[OK] %s (%s) - สร้างเงินเดือนสำเร็จ" % (
                    emp.firstname, emp.employee_code))

            except Exception as e:
                error_count += 1
                log_lines.append("[ERROR] %s (%s) - %s" % (
                    emp.firstname, emp.employee_code, str(e)))
                _logger.error("Auto payroll error for %s: %s", emp.employee_code, e)

        final_state = 'done' if error_count == 0 else 'error'
        self.write({
            'state': final_state,
            'success_count': success_count,
            'error_count': error_count,
            'log': '\n'.join(log_lines),
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

    def action_refresh_payrolls(self):
        """อัพเดตข้อมูลเงินเดือนทุกคนในรอบนี้ (คำนวณใหม่ OT/สาย/ขาด/ลา)"""
        self.ensure_one()
        if not self.payroll_ids:
            raise UserError("ยังไม่มีรายการเงินเดือนในรอบนี้ กรุณารันทำเงินเดือน Auto ก่อน")

        log_lines = []
        success_count = 0
        error_count = 0

        for payroll in self.payroll_ids:
            if payroll.manual_override:
                log_lines.append("[SKIP] %s (%s) - ปรับแก้ด้วยมือ ข้ามการอัพเดต" % (
                    payroll.employee_id.firstname, payroll.employee_code))
                continue
            try:
                # recompute "เงินได้อื่นๆ" ใหม่ก่อนเพื่อรับรายการใน other.income ที่เพิ่งยืนยัน
                payroll._compute_other_income_total()
                # ดึง API แบบ parallel (เร็วกว่า serial ~3 เท่า)
                payroll._parallel_fetch_all()
                payroll._populate_all_lines()
                # ส่งข้อมูลอัพเดตไป PHP API
                data = payroll._prepare_data_for_php()
                payroll._send_data_to_php_api('update', data)
                success_count += 1
                log_lines.append("[UPDATED] %s (%s) - อัพเดตสำเร็จ | Net=%.2f" % (
                    payroll.employee_id.firstname, payroll.employee_code, payroll.net_salary))
            except Exception as e:
                error_count += 1
                log_lines.append("[ERROR] %s (%s) - %s" % (
                    payroll.employee_id.firstname, payroll.employee_code, str(e)))
                _logger.error("Refresh payroll error for %s: %s", payroll.employee_code, e)

        timestamp = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_log = "[%s] อัพเดตข้อมูล: สำเร็จ %d, ผิดพลาด %d\n%s" % (
            timestamp, success_count, error_count, '\n'.join(log_lines))
        self.write({
            'log': new_log + '\n\n' + (self.log or ''),
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'อัพเดตข้อมูลเงินเดือน',
                'message': 'อัพเดต %d รายการ, ผิดพลาด %d รายการ' % (success_count, error_count),
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

        # 1.5) ถ้าวันนี้เป็นวัน cutoff (วันที่ 25) และยังไม่มีรอบเดือนถัดไป → สร้างรอบใหม่อัตโนมัติ
        if today.day == 25:
            current_month = today.month
            current_year = today.year
            # เดือนถัดไป
            if current_month == 12:
                next_month = 1
                next_year = str(current_year + 1)
            else:
                next_month = current_month + 1
                next_year = str(current_year)

            existing_next = self.search([
                ('month', '=', next_month),
                ('year', '=', next_year),
            ], limit=1)

            if not existing_next:
                # ดึงค่าจากรอบล่าสุดเป็นต้นแบบ
                last_period = self.search([], order='year desc, month desc', limit=1)
                cutoff_start = last_period.cutoff_start_day if last_period else 25
                cutoff_end = last_period.cutoff_end_day if last_period else 24

                import calendar
                try:
                    auto_run = date(int(next_year), next_month, cutoff_end)
                except ValueError:
                    last_day = calendar.monthrange(int(next_year), next_month)[1]
                    auto_run = date(int(next_year), next_month, min(cutoff_end, last_day))

                # payment_date = วันที่ 28 ของเดือนรอบใหม่ (เดือนเดียวกัน)
                pay_date = date(int(next_year), next_month, 28)

                self.create({
                    'month': next_month,
                    'year': next_year,
                    'cutoff_start_day': cutoff_start,
                    'cutoff_end_day': cutoff_end,
                    'auto_run_date': auto_run,
                    'payment_date': pay_date,
                    'state': 'draft',
                })
                _logger.info("[CRON] สร้างรอบใหม่อัตโนมัติ %02d/%s", next_month, next_year)

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
