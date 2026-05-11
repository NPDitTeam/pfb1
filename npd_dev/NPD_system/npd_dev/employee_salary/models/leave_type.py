# -*- coding: utf-8 -*-
import requests
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

    # เมธอดสำหรับคำนวณอายุงาน
    @api.depends('start_date')
    def _compute_work_duration(self):
        for rec in self:
            if rec.start_date:
                today = date.today()

                # หากครบหนึ่งปีแล้ว
                if today > rec.start_date + relativedelta(years=1):
                    rd = relativedelta(today, rec.start_date)
                    rec.check_y = f"ทำงานมาแล้ว {rd.years} ปี {rd.months} เดือน {rd.days} วัน"
                # หากยังไม่ครบหนึ่งปี
                else:
                    one_year_anniversary = rec.start_date + relativedelta(years=1)
                    rd = relativedelta(one_year_anniversary, today)
                    rec.check_y = f"เหลืออีก {rd.months} เดือน {rd.days} วัน จะครบ 1 ปี"
                    rec.leave_personal_paid_total = 0
                    rec.leave_vacation_total = 0
                    rec.leave_personal_paid_total_remaining = 0
                    rec.leave_vacation_total_remaining = 0
            else:
                rec.check_y = False

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
                    'leave_personal_unpaid_total_remaining': rec.leave_personal_unpaid_total,
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
            default_values = {
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
            rec.write(default_values)

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
        if res:
            self._sync_to_api('update')
        return res

    def unlink(self):
        """
        Override unlink() method to sync data to API before deletion.
        """
        for rec in self:
            rec._sync_to_api('delete')
        return super(LeaveTypeCustom, self).unlink()