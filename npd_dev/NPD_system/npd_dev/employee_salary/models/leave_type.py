# -*- coding: utf-8 -*-
import requests
import calendar
from odoo import models, fields, api
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# URL ของ API Endpoint ที่คุณสร้างไว้
API_URL = "https://npdhrms.com/api_leave_management.php"


class LeaveTypeCustom(models.Model):
    _name = 'hr.leave.type.custom'
    _description = 'ประเภทการลา'
    # เพิ่ม SQL Constraint เพื่อห้ามเพิ่ม employee_id ซ้ำ
    _sql_constraints = [
        ('employee_id_uniq', 'unique(employee_id)', 'ไม่สามารถเพิ่มข้อมูลพนักงานซ้ำได้!')
    ]
    employee_id = fields.Many2one('employee.salary', string='ชื่อพนักงาน', required=True)

    # ฟิลด์ที่ดึงข้อมูลจาก employee.salary มาแสดงโดยอัตโนมัติ
    employee_code = fields.Char(string='รหัสพนักงาน', readonly=True, related='employee_id.employee_code', required=True)
    position_id = fields.Many2one('hr.position.custom', string='ตำแหน่ง', readonly=True, related='employee_id.position_id')
    department_id = fields.Many2one('hr.department.custom', string='แผนก', readonly=True, related='employee_id.department_id')
    start_date = fields.Date(string='วันที่เริ่มงาน', readonly=True, related='employee_id.start_date', required=True)
    check_y = fields.Char(string="จำนวนวันที่ทำงาน", compute='_compute_work_duration', store=True)

    # name = fields.Char(string="ชื่อประเภทการลา", required=True)
    leave_personal_paid_used = fields.Char(string="ลากิจได้รับค่าจ้าง", default='ลากิจได้รับค่าจ้าง', required=True)
    leave_personal_paid_total_remaining = fields.Integer(string="คงเหลือ", default=3, required=True)
    leave_personal_paid_total = fields.Integer(string="ทั้งหมด", default=3, required=True)

    leave_personal_unpaid_used = fields.Char(string="ลากิจไม่ได้รับค่าจ้าง", default='ลากิจไม่ได้รับค่าจ้าง',
                                             required=True)
    leave_personal_unpaid_total_remaining = fields.Integer(string="คงเหลือ", default=30, required=True)
    leave_personal_unpaid_total = fields.Integer(string="ทั้งหมด", default=30, required=True)

    leave_sick_used = fields.Char(string="ลาป่วยมีใบรับรองแพทย์", default='ลาป่วยมีใบรับรองแพทย์', required=True)
    leave_sick_total_remaining = fields.Integer(string="คงเหลือ", default=30, required=True)
    leave_sick_total = fields.Integer(string="ทั้งหมด", default=30, required=True)

    leave_maternity_paid_used = fields.Char(string="ลาคลอดได้รับค่าจ้าง", default='ลาคลอดได้รับค่าจ้าง', required=True)
    leave_maternity_paid_total_remaining = fields.Integer(string="คงเหลือ", default=45, required=True)
    leave_maternity_paid_total = fields.Integer(string="ทั้งหมด", default=45, required=True)

    leave_maternity_unpaid_used = fields.Char(string="ลาคลอดไม่ได้รับค่าจ้าง", default='ลาคลอดไม่ได้รับค่าจ้าง',
                                              required=True)
    leave_maternity_unpaid_total_remaining = fields.Integer(string="คงเหลือ", default=45,
                                                            required=True)
    leave_maternity_unpaid_total = fields.Integer(string="ทั้งหมด", default=45,
                                                  required=True)

    leave_vacation_used = fields.Char(string="ลาพักร้อน", default='ลาพักร้อน', required=True)
    leave_vacation_total_remaining = fields.Integer(string="คงเหลือ", default=7, required=True)
    leave_vacation_total = fields.Integer(string="ทั้งหมด", default=7, required=True)

    leave_saturday_used = fields.Char(string="สิทธิหยุดวันเสาร์", default='สิทธิหยุดวันเสาร์', required=True)
    leave_saturday_total_remaining = fields.Integer(string="คงเหลือ", default=24, required=True)
    leave_saturday_total = fields.Integer(string="ทั้งหมด", default=24, required=True)

    leave_emergency_used = fields.Char(string="ฉุกเฉิน", default='ฉุกเฉิน', required=True)
    leave_emergency_total_remaining = fields.Integer(string="คงเหลือ", default=3, required=True)
    leave_emergency_total = fields.Integer(string="ทั้งหมด", default=3, required=True)

    # ---------- Helper: ค่าตั้งต้น (default) ของสิทธิ์การลาทุกประเภท ----------
    @staticmethod
    def _default_leave_values():
        """ค่าเริ่มต้นของสิทธิ์การลาทุกประเภท (ใช้ตอนรีเซ็ตขึ้นปีใหม่ / reset เอง)"""
        return {
            'leave_personal_paid_total_remaining': 3,
            'leave_personal_paid_total': 3,
            'leave_personal_unpaid_total_remaining': 30,
            'leave_personal_unpaid_total': 30,
            'leave_sick_total_remaining': 30,
            'leave_sick_total': 30,
            'leave_maternity_paid_total_remaining': 45,
            'leave_maternity_paid_total': 45,
            'leave_maternity_unpaid_total_remaining': 45,
            'leave_maternity_unpaid_total': 45,
            'leave_vacation_total_remaining': 7,
            'leave_vacation_total': 7,
            'leave_saturday_total_remaining': 24,
            'leave_saturday_total': 24,
            'leave_emergency_total_remaining': 3,
            'leave_emergency_total': 3,
        }

    # ---------- Helper: ข้อความสรุปอายุงาน ----------
    @staticmethod
    def _work_duration_text(start_date, today):
        if not start_date:
            return False
        # ครบ 1 ปีแล้ว (รวมวันครบรอบพอดี)
        if today >= start_date + relativedelta(years=1):
            rd = relativedelta(today, start_date)
            return f"ทำงานมาแล้ว {rd.years} ปี {rd.months} เดือน {rd.days} วัน"
        # ยังไม่ครบ 1 ปี
        one_year_anniversary = start_date + relativedelta(years=1)
        rd = relativedelta(one_year_anniversary, today)
        return f"เหลืออีก {rd.months} เดือน {rd.days} วัน จะครบ 1 ปี"

    # ---------- Helper: จำนวนวันลากิจได้รับค่าจ้าง (ได้สิทธิ์เมื่อครบ 3 เดือน) ----------
    @staticmethod
    def _personal_paid_days(start_date, today):
        if start_date and today >= start_date + relativedelta(months=3):
            return 3
        return 0

    # ---------- Helper: จำนวนวันลาพักร้อน ----------
    @staticmethod
    def _vacation_days(start_date, today):
        """ครบ 1 ปี ได้ 7 วัน/ปี — ปีแรกที่ครบ (กลางปี) ปันส่วนตามเดือนที่เหลือในปีปฏิทิน (ปัดลง)"""
        if not start_date:
            return 0
        anniversary = start_date + relativedelta(years=1)  # วันที่เริ่มมีสิทธิ์ครั้งแรก
        if today < anniversary:
            return 0
        # ปีปฏิทินที่ครบ 1 ปีพอดี → ปันส่วนตามเดือนที่เหลือ (นับเดือนครบรอบด้วย)
        if today.year == anniversary.year:
            remaining_months = 12 - anniversary.month + 1
            return 7 * remaining_months // 12  # ปัดลง (floor)
        # ปีปฏิทินถัด ๆ ไป → เต็ม 7 วัน
        return 7

    # ---------- รวมค่าสิทธิ์การลาที่ต้องอัพเดทประจำวันของ record นี้ ----------
    def _entitlement_vals(self, today, reset_all=False, force_remaining=False):
        """คืน dict ค่าที่ต้องเขียนลง record ตามวันที่ today

        หลักการแยกเจ้าของค่า:
        - "ทั้งหมด" (total) = สิทธิ์ตามอายุงาน → Odoo เป็นเจ้าของ อัพเดททุกวันได้
        - "คงเหลือ" (remaining) = วันที่ใช้จริง → แอป checkin/PHP เป็นเจ้าของ
          cron วันธรรมดา "ห้ามแตะ" คงเหลือ (กันทับค่าที่แอปหักไป)

        เขียน "คงเหลือ" เฉพาะกรณี:
        - reset_all=True       → ขึ้นปีใหม่ คืนคงเหลือเต็มตามสิทธิ์
        - force_remaining=True  → ตอนสร้าง record / แก้วันเริ่มงาน (ยังไม่มีการใช้วันลา)
        - เพิ่งได้สิทธิ์ใหม่     → total เดิม 0 แล้ววันนี้ได้สิทธิ์ (0→3 หรือ 0→7)
        """
        self.ensure_one()
        vals = {}
        if reset_all:
            vals.update(self._default_leave_values())

        # อายุงาน
        vals['check_y'] = self._work_duration_text(self.start_date, today)

        # ลากิจได้รับค่าจ้าง — ครบ 3 เดือน ได้สิทธิ์ 3 (ไม่ถึง = 0)
        paid = self._personal_paid_days(self.start_date, today)
        vals['leave_personal_paid_total'] = paid
        if reset_all or force_remaining or (self.leave_personal_paid_total == 0 and paid > 0):
            vals['leave_personal_paid_total_remaining'] = paid

        # ลาพักร้อน — ครบ 1 ปี ปันส่วนตามเดือน
        vac = self._vacation_days(self.start_date, today)
        vals['leave_vacation_total'] = vac
        if reset_all or force_remaining or (self.leave_vacation_total == 0 and vac > 0):
            vals['leave_vacation_total_remaining'] = vac
        return vals

    # เมธอดสำหรับคำนวณอายุงาน
    @api.depends('start_date')
    def _compute_work_duration(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.start_date:
                rec.check_y = False
                continue
            vals = rec._entitlement_vals(today, force_remaining=True)
            rec.check_y = vals['check_y']
            rec.leave_personal_paid_total = vals['leave_personal_paid_total']
            rec.leave_personal_paid_total_remaining = vals['leave_personal_paid_total_remaining']
            rec.leave_vacation_total = vals['leave_vacation_total']
            rec.leave_vacation_total_remaining = vals['leave_vacation_total_remaining']

    # ---------- Scheduled Action: อัพเดทสิทธิ์การลารายวัน ----------
    @api.model
    def _cron_update_leave_entitlements(self):
        """อัพเดทอายุงาน + ลากิจ(3เดือน) + ลาพักร้อน(1ปี ปันส่วน) ทุกวัน
        เฉพาะพนักงานสถานะ 'ใช้งาน' หรือ 'ไม่ใช้งาน' ที่ออกจากงานในรอบทำเงินปัจจุบัน (25→24)
        ขึ้นปีใหม่ (1 ม.ค.) รีเซ็ตสิทธิ์การลาทุกประเภทเป็นค่าตั้งต้น
        """
        today = fields.Date.context_today(self)

        # ---- คำนวณวันเริ่มรอบทำเงินปัจจุบัน (รอบ 25→24, ดีฟอลต์ start_day=25) ----
        #   รอบคร่อม 2 เดือน: ตั้งแต่วันที่ 25 ของเดือนหนึ่ง ถึงวันที่ 24 ของเดือนถัดไป
        #   - วันนี้ >= 25 → อยู่ในรอบที่เริ่ม "วันที่ 25 ของเดือนนี้" (รอบขยับไปเดือนถัดไปแล้ว)
        #   - วันนี้ <  25 → อยู่ในรอบที่เริ่ม "วันที่ 25 ของเดือนก่อนหน้า"
        start_day = 25
        period = self.env['payroll.period'].search([], limit=1, order='id desc')
        if period and getattr(period, 'cutoff_start_day', 0):
            start_day = period.cutoff_start_day
        if today.day >= start_day:
            cyc_m, cyc_y = today.month, today.year
        elif today.month == 1:
            cyc_m, cyc_y = 12, today.year - 1
        else:
            cyc_m, cyc_y = today.month - 1, today.year
        last_cyc = calendar.monthrange(cyc_y, cyc_m)[1]
        cycle_start = date(cyc_y, cyc_m, min(start_day, last_cyc))

        is_new_year = (today.month == 1 and today.day == 1)

        # ---- 1) ดึง "คงเหลือ" ล่าสุดจาก PHP เข้ามาก่อน (PHP = เจ้าของค่าคงเหลือ) ----
        #     ใช้ skip_api_sync กัน push ย้อนกลับระหว่าง pull, และ try/except กัน API ล่ม
        #     หลัง pull แล้ว Odoo.คงเหลือ == PHP.คงเหลือ → ตอน push อัพเดทจะไม่ทับค่าที่แอปหัก
        try:
            self.with_context(skip_api_sync=True).sync_all_from_api()
        except Exception as e:
            _logger.warning("ดึงข้อมูลคงเหลือจาก PHP ก่อนอัพเดทล้มเหลว (ข้ามขั้นตอน pull): %s", e)

        # ---- 2) อัพเดท "ทั้งหมด" + อายุงาน (คงเหลือแตะเฉพาะปีใหม่/เพิ่งได้สิทธิ์) ----
        updated = 0
        for rec in self.search([]):
            emp = rec.employee_id
            if not emp:
                continue
            # active ทุกคน + inactive ที่ resign_date อยู่ในรอบทำเงินปัจจุบัน
            eligible = emp.status == 'active' or (
                emp.status == 'inactive' and emp.resign_date and emp.resign_date >= cycle_start
            )
            if not eligible:
                continue
            vals = rec._entitlement_vals(today, reset_all=is_new_year)
            try:
                rec.write(vals)
                updated += 1
            except Exception as e:
                # API sync ล่ม/ผิดพลาด — ข้าม record นี้ ไม่ให้ล้มทั้ง cron
                _logger.warning("อัพเดทสิทธิ์การลาล้มเหลว record id=%s: %s", rec.id, e)
        _logger.info("Leave entitlement cron: อัพเดท %s รายการ (new_year=%s)", updated, is_new_year)
        return True

    def _sync_to_api(self, action):
        """
        เมธอดสำหรับส่งข้อมูลไปยัง PHP API Endpoint
        """
        for rec in self:
            try:
                # จัดเตรียมข้อมูลที่จะส่งในรูปแบบ JSON
                payload = {
                    'action': action,
                    'id': rec.id,
                    'employee_id': rec.employee_id.id if rec.employee_id else None,
                    'employee_name': (rec.employee_id.firstname or '') + ' ' + (rec.employee_id.lastname or '') if rec.employee_id else None,
                    'employee_code': rec.employee_code,
                    'position': rec.position_id.name if rec.position_id else None,
                    'department': rec.department_id.name if rec.department_id else None,
                    'start_date': rec.start_date.isoformat() if rec.start_date else None,
                    'leave_personal_paid_used': rec.leave_personal_paid_used,
                    'leave_personal_paid_total_remaining': rec.leave_personal_paid_total_remaining,
                    'leave_personal_paid_total': rec.leave_personal_paid_total,
                    'leave_personal_unpaid_used': rec.leave_personal_unpaid_used,
                    'leave_personal_unpaid_total_remaining': rec.leave_personal_unpaid_total_remaining,
                    'leave_personal_unpaid_total': rec.leave_personal_unpaid_total,
                    'leave_sick_used': rec.leave_sick_used,
                    'leave_sick_total_remaining': rec.leave_sick_total_remaining,
                    'leave_sick_total': rec.leave_sick_total,
                    'leave_maternity_paid_used': rec.leave_maternity_paid_used,
                    'leave_maternity_paid_total_remaining': rec.leave_maternity_paid_total_remaining,
                    'leave_maternity_paid_total': rec.leave_maternity_paid_total,
                    'leave_maternity_unpaid_used': rec.leave_maternity_unpaid_used,
                    'leave_maternity_unpaid_total_remaining': rec.leave_maternity_unpaid_total_remaining,
                    'leave_maternity_unpaid_total': rec.leave_maternity_unpaid_total,
                    'leave_vacation_used': rec.leave_vacation_used,
                    'leave_vacation_total_remaining': rec.leave_vacation_total_remaining,
                    'leave_vacation_total': rec.leave_vacation_total,
                    'leave_saturday_used': rec.leave_saturday_used,
                    'leave_saturday_total_remaining': rec.leave_saturday_total_remaining,
                    'leave_saturday_total': rec.leave_saturday_total,
                    'leave_emergency_used': rec.leave_emergency_used,
                    'leave_emergency_total_remaining': rec.leave_emergency_total_remaining,
                    'leave_emergency_total': rec.leave_emergency_total,
                }

                # ส่งข้อมูลแบบ POST ไปยัง API
                response = requests.post(API_URL, json=payload)
                response.raise_for_status()

                api_response = response.json()
                if api_response.get('status') == 'success':
                    _logger.info("Successfully synced to API for record ID %s with action: %s", rec.id, action)
                else:
                    _logger.error("API sync failed for record ID %s. Message: %s", rec.id, api_response.get('message'))
                    raise UserError(f"การซิงค์ข้อมูลล้มเหลว: {api_response.get('message') or 'ไม่ทราบสาเหตุ'}")

            except requests.exceptions.RequestException as e:
                _logger.error("Failed to connect to API for record ID %s: %s", rec.id, e)
                raise UserError(f"ไม่สามารถเชื่อมต่อกับ API ได้: {e}")
            except Exception as e:
                _logger.error("An unexpected error occurred during API sync for record ID %s: %s", rec.id, e)
                raise UserError(f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}")

    @api.model
    def sync_all_from_api(self):
        """
        เมธอดสำหรับดึงและอัปเดตข้อมูลทั้งหมดจาก PHP API Endpoint
        """
        _logger.info("Starting sync from PHP API...")
        try:
            response = requests.get(API_URL)
            response.raise_for_status()

            api_response = response.json()

            if api_response.get('status') == 'success' and 'data' in api_response:
                php_records = api_response['data']
                _logger.info("Successfully fetched %d records from PHP API.", len(php_records))

                php_data_map = {int(rec['id']): rec for rec in php_records}
                odoo_records = self.env['hr.leave.type.custom'].search([('id', 'in', list(php_data_map.keys()))])

                for odoo_rec in odoo_records:
                    php_data = php_data_map.get(odoo_rec.id)
                    if php_data:
                        vals = {
                            'leave_personal_paid_used': php_data.get('leave_personal_paid_used'),
                            'leave_personal_paid_total_remaining': int(
                                php_data.get('leave_personal_paid_total_remaining', 0)),
                            'leave_personal_paid_total': int(php_data.get('leave_personal_paid_total', 0)),
                            'leave_personal_unpaid_used': php_data.get('leave_personal_unpaid_used'),
                            'leave_personal_unpaid_total_remaining': int(
                                php_data.get('leave_personal_unpaid_total_remaining', 0)),
                            'leave_personal_unpaid_total': int(php_data.get('leave_personal_unpaid_total', 0)),
                            'leave_sick_used': php_data.get('leave_sick_used'),
                            'leave_sick_total_remaining': int(php_data.get('leave_sick_total_remaining', 0)),
                            'leave_sick_total': int(php_data.get('leave_sick_total', 0)),
                            'leave_maternity_paid_used': php_data.get('leave_maternity_paid_used'),
                            'leave_maternity_paid_total_remaining': int(
                                php_data.get('leave_maternity_paid_total_remaining', 0)),
                            'leave_maternity_paid_total': int(php_data.get('leave_maternity_paid_total', 0)),
                            'leave_maternity_unpaid_used': php_data.get('leave_maternity_unpaid_used'),
                            'leave_maternity_unpaid_total_remaining': int(
                                php_data.get('leave_maternity_unpaid_total_remaining', 0)),
                            'leave_maternity_unpaid_total': int(php_data.get('leave_maternity_unpaid_total', 0)),
                            'leave_vacation_used': php_data.get('leave_vacation_used'),
                            'leave_vacation_total_remaining': int(php_data.get('leave_vacation_total_remaining', 0)),
                            'leave_vacation_total': int(php_data.get('leave_vacation_total', 0)),
                            'leave_saturday_used': php_data.get('leave_saturday_used'),
                            'leave_saturday_total_remaining': int(php_data.get('leave_saturday_total_remaining', 0)),
                            'leave_saturday_total': int(php_data.get('leave_saturday_total', 0)),
                            'leave_emergency_used': php_data.get('leave_emergency_used'),
                            'leave_emergency_total_remaining': int(php_data.get('leave_emergency_total_remaining', 0)),
                            'leave_emergency_total': int(php_data.get('leave_emergency_total', 0)),
                        }
                        odoo_rec.write(vals)

            else:
                _logger.error("API call failed. Message: %s", api_response.get('message', 'No message provided.'))
                raise UserError(f"การดึงข้อมูลล้มเหลว: {api_response.get('message') or 'ไม่ทราบสาเหตุ'}")

        except requests.exceptions.RequestException as e:
            _logger.error("Failed to connect to API: %s", e)
            raise UserError(f"ไม่สามารถเชื่อมต่อกับ API ได้: {e}")
        except Exception as e:
            _logger.error("An unexpected error occurred during API sync: %s", e)
            raise UserError(f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}")

    @api.model
    def sync_and_open_view(self):
        """
        เมธอดสำหรับซิงค์ข้อมูลและส่งคืน action เพื่อเปิดหน้า view
        """
        self.sync_all_from_api()
        # คืน action เพื่อเปิดหน้าต่าง
        return self.env.ref('employee_salary.action_leave_type').read()[0]

    # ========== Start: New Method Added ==========
    def update_and_reset_to_default(self):
        """
        เมธอดสำหรับอัปเดตอายุงานและรีเซ็ตค่าวันลาเป็นค่าเริ่มต้น
        """
        for rec in self:
            # 1. รีเซ็ตค่าวันลาทั้งหมดให้เป็นค่าตาม default ของโมเดล
            rec.write(self._default_leave_values())

            # 2. เรียกใช้เมธอดคำนวณอายุงานอีกครั้ง
            #    ซึ่งจะอัปเดตฟิลด์ check_y และปรับค่าวันลาพักร้อน/ลากิจตามเงื่อนไขอายุงานไม่ถึง 1 ปี
            rec._compute_work_duration()

        # การเรียกใช้ rec.write() จะไปเรียกใช้เมธอด write() ที่ถูก override ไว้อัตโนมัติ
        # ซึ่งในนั้นมีการเรียก _sync_to_api('update') อยู่แล้ว จึงไม่จำเป็นต้องเรียกซ้ำ
        return True

    # ========== End: New Method Added ==========

    @api.model
    def create(self, vals):
        """
        Override create() method to sync data to API after creation.
        """
        record = super(LeaveTypeCustom, self).create(vals)
        record._sync_to_api('create')
        return record

    def write(self, vals):
        """
        Override write() method to sync data to API after update.
        """
        # หากมีการเรียก _compute_work_duration แยกต่างหาก อาจทำให้เกิดการเขียนซ้ำซ้อน
        # ตรวจสอบว่ามีการอัปเดต start_date หรือไม่ เพื่อเรียก _compute_work_duration
        if 'start_date' in vals:
            self._compute_work_duration()

        res = super(LeaveTypeCustom, self).write(vals)
        # skip_api_sync=True → ไม่ push กลับ PHP (ใช้ตอน pull ค่าคงเหลือเข้ามาใน cron)
        if res and not self.env.context.get('skip_api_sync'):
            self._sync_to_api('update')
        return res

    def unlink(self):
        """
        Override unlink() method to sync data to API before deletion.
        """
        for rec in self:
            rec._sync_to_api('delete')
        return super(LeaveTypeCustom, self).unlink()