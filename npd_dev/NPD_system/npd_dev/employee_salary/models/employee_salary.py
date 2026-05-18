# -*- coding: utf-8 -*-
import requests
import json
from odoo import models, fields, api
import logging
from odoo.exceptions import UserError
from datetime import date

_logger = logging.getLogger(__name__)

# Add a configuration variable for the API endpoint URL
API_URL = "https://npdhrms.com/export_data.php"
CRUD_API_URL = "https://npdhrms.com/api_employee_salary.php"  # URL ใหม่สำหรับ CRUD


class EmployeeSalary(models.Model):
    _name = 'employee.salary'
    _description = 'Employee Salary'
    _rec_name = 'firstname'

    _sql_constraints = [
        ('employee_code_uniq', 'unique(employee_code)', 'ไม่สามารถเพิ่มข้อมูลพนักงานซ้ำได้!')
    ]

    HRMS_COMPANY = [
        ("นภดลเอสกรุ๊ปจำกัด", "นภดลเอสกรุ๊ปจำกัด"),
        ("เอ็นพีดีสตีลเทคจำกัด", "เอ็นพีดีสตีลเทคจำกัด"),
        ("เอ็นพีดีโลจิสติกส์จำกัด", "เอ็นพีดีโลจิสติกส์จำกัด"),
        ("นภดลกรุงเทพจำกัด", "นภดลกรุงเทพจำกัด"),
        ("นภดลอินเตอร์เทรดดิ้งจำกัด", "นภดลอินเตอร์เทรดดิ้งจำกัด"),
    ]

    employee_code = fields.Char(string='รหัสพนักงาน')
    fingerprint_id = fields.Char(string='รหัสลายนิ้วมือ')
    pin = fields.Char(string='PIN 6 หลัก')
    prefix_th = fields.Selection([('นาย', 'นาย'), ('นางสาว', 'นางสาว'), ('นาง', 'นาง')], string='คำนำหน้าชื่อ')
    nationality = fields.Selection([('ไทย', 'ไทย'), ('ต่างชาติ', 'ต่างชาติ')], string='สัญชาติ')
    allow_offsite_time = fields.Boolean(string='อนุญาตลงเวลานอกสถานที่')
    gender = fields.Selection([('ชาย', 'ชาย'), ('หญิง', 'หญิง')], string='เพศ')

    device_id = fields.Char(string='Device ID')
    allow_multi_login = fields.Boolean(string='อนุญาตเข้าพร้อมกัน', default=False)

    # Employee Image (local only, not synced to API)
    employee_image = fields.Binary(string='รูปภาพพนักงาน', attachment=True)

    # Fields that should NOT be synced to external API
    SKIP_API_FIELDS = {'employee_image', 'behavior_ids', 'work_history_image_ids'}

    # Personal Information
    firstname = fields.Char(string='ชื่อ')
    lastname = fields.Char(string='นามสกุล')
    nickname = fields.Char(string='ชื่อเล่น')
    firstname_eng = fields.Char(string='ชื่อ (ENG)')
    lastname_eng = fields.Char(string='นามสกุล (ENG)')

    # เปลี่ยนจาก Char เป็น Many2one สำหรับสาขา
    branch_id = fields.Many2one('hr.branch.custom', string='สาขา')

    marital_status = fields.Selection([('โสด', 'โสด'), ('สมรส', 'สมรส'), ('หย่า', 'หย่า')], string='สถานะ')
    personal_equipment = fields.Char(string='อุปกรณ์เบิกประจำตัว')
    line_id = fields.Char(string='LineID ส่วนตัว')
    birthdate = fields.Date(string='วันเกิด')
    age = fields.Integer(string='อายุ')
    phone_number = fields.Char(string='เบอร์โทรศัพท์')
    email = fields.Char(string='อีเมล')
    id_card_number = fields.Char(string='เลขประจำตัวประชาชน')
    passport_number = fields.Char(string='เลขที่หนังสือเดินทาง')
    social_security_number = fields.Char(string='ประกันสังคม')
    address = fields.Char(string='ที่อยู่')

    # เปลี่ยนจาก Selection เป็น Many2one
    position_id = fields.Many2one('hr.position.custom', string='ตำแหน่ง')
    department_id = fields.Many2one('hr.department.custom', string='แผนก')

    company = fields.Selection(selection=HRMS_COMPANY, string='บริษัท')
    employee_type = fields.Selection([('ประจำ', 'ประจำ'), ('ทดลองงาน', 'ทดลองงาน'), ('รายวัน', 'รายวัน')],
                                     string='ประเภทพนักงาน')
    salary = fields.Float(string='ค่าจ้าง')

    # ค่าคงที่ของประกันสังคมไทย (ใช้ใน auto-calc)
    SSO_RATE = 0.05
    SSO_MIN_WAGE = 1650.0
    SSO_MAX_WAGE = 17500.0

    advance_payment_type = fields.Selection([('ค่าเดินทาง', 'ค่าเดินทาง'), ('ค่าเบี้ยเลี้ยง', 'ค่าเบี้ยเลี้ยง')],
                                            string='เงินเบิกล่วงหน้า')
    advance_payment_limit = fields.Float(string='วงเงินเบิกล่วงหน้า')

    # Financial Information
    enable_social_security = fields.Boolean(string='ประกันสังคม', default=True)
    social_security_condition = fields.Selection(
        [('คิดตามฐานเงินเดือนจริงที่ได้รับ', 'คิดตามฐานเงินเดือนจริงที่ได้รับ')], string='เงื่อนไขประกันสังคม')
    social_security_fixed_amount = fields.Float(string='ค่าคงที่ของประกันสังคม')
    social_security_start_date = fields.Date(string='เงื่อนไขที่เริ่มคำนวณประกันสังคม')

    @api.onchange('salary')
    def _onchange_salary_set_sso(self):
        """เมื่อกรอก/เปลี่ยน salary → set เงื่อนไข + ค่าคงที่ประกันสังคมอัตโนมัติ
        - เงื่อนไข = 'คิดตามฐานเงินเดือนจริงที่ได้รับ' (default)
        - ค่าคงที่ = clamp(salary, 1650, 17500) × 5% (สูงสุด 875)
        """
        for rec in self:
            if rec.salary and rec.salary > 0:
                if not rec.social_security_condition:
                    rec.social_security_condition = 'คิดตามฐานเงินเดือนจริงที่ได้รับ'
                effective_wage = max(min(rec.salary, self.SSO_MAX_WAGE), self.SSO_MIN_WAGE)
                rec.social_security_fixed_amount = round(effective_wage * self.SSO_RATE, 2)
    enable_tax = fields.Boolean(string='ภาษี', default=True)
    tax_condition = fields.Selection([('คิดภาษี ภงด.1 ใหม่ทุกเดือน', 'คิดภาษี ภงด.1 ใหม่ทุกเดือน')],
                                     string='เงื่อนไขภาษี')
    tax_exception = fields.Float(string='จำนวนภาษีคงที่ต่อเดือน')
    tax_start_date_condition = fields.Date(string='เงื่อนไขที่เริ่มคำนวณภาษี')

    # Work Behavior
    behavior_ids = fields.One2many('employee.work.behavior', 'employee_id', string='พฤติกรรมการทำงาน')

    # Work History Images
    work_history_image_ids = fields.One2many('employee.work.history.image', 'employee_id',
                                             string='รูปภาพประวัติการทำงาน')

    # Work Information
    start_date = fields.Date(string='วันที่เริ่มงาน')
    appointment_date = fields.Date(string='วันที่บรรจุ')
    contract_end_date = fields.Date(string='วันที่สิ้นสุดสัญญาจ้าง')
    end_trial_date = fields.Date(string='วันที่สิ้นสุดทดลองงาน')
    probation_period = fields.Integer(string='ระยะเวลาทดลองงาน (วัน)')
    retirement_year = fields.Date(string='ปีที่เกษียณ')

    # Bank Account
    payment_channel = fields.Selection([('เงินสด', 'เงินสด'), ('โอนผ่านธนาคาร', 'โอนผ่านธนาคาร')],
                                       string='ช่องทางการชำระเงิน')
    payment_account_type = fields.Selection([('B0001 SCB SCB', 'B0001 SCB SCB')], string='บัญชีบริษัทนำจ่าย')

    bank_name = fields.Selection([
        ('KBANK', 'KBANK - ธนาคารกสิกรไทย'),
        ('BBL', 'BBL - ธนาคารกรุงเทพ'),
        ('KTB', 'KTB - ธนาคารกรุงไทย'),
        ('SCB', 'SCB - ธนาคารไทยพาณิชย์'),
        ('BAY', 'BAY - ธนาคารกรุงศรีอยุธยา'),
        ('TTB', 'TTB - ธนาคารทหารไทยธนชาต'),
        ('GSB', 'GSB - ธนาคารออมสิน'),
        ('UOB', 'UOB - ธนาคารยูโอบี'),
        ('CIMBT', 'CIMB - ธนาคารซีไอเอ็มบีไทย'),
        ('KKP', 'KKP - ธนาคารเกียรตินาคินภัทร'),
        ('LHBANK', 'LHBANK - ธนาคารแลนด์ แอนด์ เฮ้าส์'),
        ('TISCO', 'TISCO - ธนาคารทิสโก้'),
        ('BAAC', 'BAAC - ธ.ก.ส.'),
        ('GHB', 'GHB - ธอส.'),
        ('ISBT', 'ISBT - ธนาคารอิสลามแห่งประเทศไทย'),
        ('PROMPTPAY', 'PromptPay - พร้อมเพย์'),
    ], string='ธนาคาร')

    bank_branch_code = fields.Char(string='รหัสสาขาธนาคาร')
    bank_account_number = fields.Char(string='เลขที่บัญชี')
    details = fields.Text(string='รายละเอียด')

    status = fields.Selection(
        [
            ('active', 'ใช้งาน'),
            ('inactive', 'ไม่ใช้งาน')
        ],
        string='สถานะการใช้งาน',
        default='active'
    )

    check_date_up_device_id = fields.Date(string='อัพเดท device_id', default=lambda self: date.today(),
                                          compute='_compute_fetch_device_id_from_php')

    # Other Income Fields
    cost_of_living = fields.Float(string='เงินค่าครองชีพ')
    position_allowance = fields.Float(string='เงินประจำตำแหน่ง')
    experience_allowance = fields.Float(string='เงินค่าประสบการณ์')
    professional_allowance = fields.Float(string='เงินค่าวิชาชีพ')
    auto_payroll = fields.Boolean(string='ทำเงินเดือน Auto', default=True,
                                  help='ถ้าติ๊ก ระบบจะคำนวณเงินเดือนให้อัตโนมัติ ถ้าไม่ติ๊ก ต้องทำมือ')

    def _prepare_data_for_api(self, record):
        """
        เมธอดช่วยเตรียมข้อมูลสำหรับส่งไปยัง API
        ส่งชื่อ position, department และ branch แทน ID
        """
        vals = {
            'employee_code': record.employee_code,
            'fingerprint_id': record.fingerprint_id,
            'username': record.employee_code,
            'password': record.pin,
            'prefix_th': record.prefix_th,
            'firstname': record.firstname,
            'lastname': record.lastname,
            'nickname': record.nickname,
            'firstname_eng': record.firstname_eng,
            'lastname_eng': record.lastname_eng,
            # ส่งชื่อแทน ID เพื่อให้ API ไม่ error
            'branch': record.branch_id.name if record.branch_id else None,
            'department': record.department_id.name if record.department_id else None,
            'position': record.position_id.name if record.position_id else None,
            'gender': record.gender,
            'nationality': record.nationality,
            'marital_status': record.marital_status,
            'birthdate': record.birthdate.isoformat() if record.birthdate else None,
            'age': record.age,
            'phone_number': record.phone_number,
            'email': record.email,
            'id_card_number': record.id_card_number,
            'passport_number': record.passport_number,
            'social_security_number': record.social_security_number,
            'employee_type': record.employee_type,
            'salary': record.salary,
            'advance_payment_type': record.advance_payment_type,
            'advance_payment_limit': record.advance_payment_limit,
            'start_date': record.start_date.isoformat() if record.start_date else None,
            # resign_date เป็นฟิลด์จาก work_security_deposit (_inherit) — ใช้ getattr กันพลาด
            'resign_date': (getattr(record, 'resign_date', False).isoformat()
                            if getattr(record, 'resign_date', False) else None),
            'appointment_date': record.appointment_date.isoformat() if record.appointment_date else None,
            'contract_end_date': record.contract_end_date.isoformat() if record.contract_end_date else None,
            'end_trial_date': record.end_trial_date.isoformat() if record.end_trial_date else None,
            'probation_period': record.probation_period,
            'retirement_year': record.retirement_year.isoformat() if record.retirement_year else None,
            'payment_channel': record.payment_channel,
            'payment_account_type': record.payment_account_type,
            'bank_name': record.bank_name,
            'bank_branch_code': record.bank_branch_code,
            'bank_account_number': record.bank_account_number,
            'details': record.details,
            'allow_offsite_time': record.allow_offsite_time,
            'allow_multi_login': record.allow_multi_login,
            'company': record.company,
            'enable_social_security': record.enable_social_security,
            'social_security_condition': record.social_security_condition,
            'social_security_fixed_amount': record.social_security_fixed_amount,
            'social_security_start_date': record.social_security_start_date.isoformat() if record.social_security_start_date else None,
            'enable_tax': record.enable_tax,
            'tax_condition': record.tax_condition,
            'tax_exception': record.tax_exception,
            'tax_start_date_condition': record.tax_start_date_condition.isoformat() if record.tax_start_date_condition else None,
            'status': record.status,
            'cost_of_living': record.cost_of_living,
            'position_allowance': record.position_allowance,
            'experience_allowance': record.experience_allowance,
            'professional_allowance': record.professional_allowance,
        }

        # MySQL บางคอลัมน์เป็น NOT NULL (เช่น social_security_condition)
        # แทน None ด้วย '' สำหรับ Selection/Char เพื่อกัน integrity error
        not_null_str_fields = ['social_security_condition']
        for f in not_null_str_fields:
            if vals.get(f) is None:
                vals[f] = ''
        return vals

    def _get_position_by_name(self, name):
        """ค้นหา position_id จากชื่อ"""
        if not name:
            return False
        position = self.env['hr.position.custom'].search([('name', '=', name)], limit=1)
        if not position:
            # สร้างใหม่ถ้าไม่พบ
            position = self.env['hr.position.custom'].with_context(skip_api_sync=True).create(
                {'name': name, 'is_active': True})
        return position.id

    def _get_department_by_name(self, name):
        """ค้นหา department_id จากชื่อ"""
        if not name:
            return False
        department = self.env['hr.department.custom'].search([('name', '=', name)], limit=1)
        if not department:
            # สร้างใหม่ถ้าไม่พบ
            department = self.env['hr.department.custom'].with_context(skip_api_sync=True).create(
                {'name': name, 'is_active': True})
        return department.id

    def _get_branch_by_name(self, name):
        """ค้นหา branch_id จากชื่อ"""
        if not name:
            return False
        branch = self.env['hr.branch.custom'].search([('name', '=', name)], limit=1)
        if not branch:
            # สร้างใหม่ถ้าไม่พบ
            branch = self.env['hr.branch.custom'].with_context(skip_api_sync=True).create(
                {'name': name, 'is_active': True})
        return branch.id

    def _sync_to_api(self, action, values=None):
        """
        เมธอดสำหรับส่งข้อมูลไปยัง PHP API Endpoint สำหรับการดำเนินการ CRUD
        """
        for rec in self:
            try:
                payload = {'action': action}
                if action == 'delete' or action == 'update':
                    payload['values'] = {'employee_code': rec.employee_code}
                else:
                    payload['values'] = rec._prepare_data_for_api(rec)

                if action == 'update':
                    payload['values'] = {**payload['values'], **rec._prepare_data_for_api(rec)}

                response = requests.post(CRUD_API_URL, json=payload)
                response.raise_for_status()

                api_response = response.json()
                if api_response.get('status') == 'success':
                    _logger.info("Successfully synced to API for record ID %s with action: %s", rec.id, action)
                else:
                    _logger.error("API sync failed for record ID %s. Message: %s", rec.id, api_response.get('message'))
                    raise UserError(
                        f"API sync failed for record ID {rec.id}. Message: {api_response.get('message') or 'Unknown error'}")

            except requests.exceptions.RequestException as e:
                _logger.error("Failed to connect to API for record ID %s: %s", rec.id, e)
                raise UserError(f"Failed to connect to API for record ID {rec.id}: {e}")
            except Exception as e:
                _logger.error("An unexpected error occurred during API sync for record ID %s: %s", rec.id, e)
                raise UserError(f"An unexpected error occurred during API sync for record ID {rec.id}: {e}")

    def reset_device_id(self):
        """
        เมธอดสำหรับอัปเดต device_id เป็นค่าว่างในฐานข้อมูล PHP
        """
        for record in self:
            print("employee_code", record.employee_code)
            if not record:
                raise UserError("ไม่พบข้อมูลพนักงานสำหรับรหัสพนักงานนี้")

            try:
                payload = {
                    'action': 'update',
                    'values': {
                        'employee_code': record.employee_code,
                        'device_id': ''
                    }
                }
                response = requests.post(CRUD_API_URL, json=payload)
                response.raise_for_status()

                api_response = response.json()
                if api_response.get('status') == 'success':
                    record.write({'device_id': False})
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'สำเร็จ',
                            'message': 'รีเซ็ต Device ID สำเร็จ',
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    raise UserError(f"ไม่สามารถรีเซ็ต Device ID ได้: {api_response.get('message') or 'ไม่ทราบสาเหตุ'}")

            except requests.exceptions.RequestException as e:
                raise UserError(f"ไม่สามารถเชื่อมต่อกับ API ได้: {e}")
            except Exception as e:
                raise UserError(f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}")

    @api.depends('device_id')
    def _compute_fetch_device_id_from_php(self):
        from datetime import date
        for rec in self:
            rec.check_date_up_device_id = date.today()
            if rec.employee_code:
                try:
                    url = f"https://npdhrms.com/get_device_id.php?employee_code={rec.employee_code}"
                    response = requests.get(url, timeout=10)
                    data = response.json()
                    if data.get("status") == "success":
                        device_id = data.get("device_id")
                        if device_id:
                            rec.device_id = device_id
                            rec.check_date_up_device_id = date.today()

                except Exception as e:
                    _logger.error(f"❌ Error fetching device_id for {rec.employee_code}: {e}")

    @api.model
    def create(self, vals):
        record = super(EmployeeSalary, self).create(vals)
        record._sync_to_api('create')
        return record

    def write(self, vals):
        res = super(EmployeeSalary, self).write(vals)
        if res and not set(vals.keys()).issubset(self.SKIP_API_FIELDS):
            self._sync_to_api('update', values=vals)
        return res

    def unlink(self):
        for rec in self:
            rec._sync_to_api('delete')
        return super(EmployeeSalary, self).unlink()

    def import_from_php(self):
        try:
            _logger.info("Attempting to fetch data from API: %s", API_URL)
            response = requests.get(API_URL)
            response.raise_for_status()

            data = response.json()
            _logger.info("Data successfully fetched. Status: %s", data.get('status'))

            if data.get('status') != 'success' or not isinstance(data.get('data'), list):
                _logger.error("Invalid data format from API: %s", data)
                raise Exception("Invalid data received from the API.")

            for record_data in data['data']:
                employee_code = record_data.get('employee_code')

                if employee_code:
                    existing_record = self.search([('employee_code', '=', employee_code)], limit=1)

                    # แปลงชื่อ position, department และ branch เป็น ID
                    position_id = self._get_position_by_name(record_data.get('position'))
                    department_id = self._get_department_by_name(record_data.get('department'))
                    branch_id = self._get_branch_by_name(record_data.get('branch'))

                    values = {
                        'employee_code': record_data.get('employee_code'),
                        'fingerprint_id': record_data.get('fingerprint_id'),
                        'pin': record_data.get('password'),
                        'prefix_th': record_data.get('prefix_th'),
                        'nationality': record_data.get('nationality'),
                        'allow_offsite_time': record_data.get('allow_offsite_time'),
                        'allow_multi_login': record_data.get('allow_multi_login'),
                        'gender': record_data.get('gender'),
                        'firstname': record_data.get('firstname'),
                        'lastname': record_data.get('lastname'),
                        'nickname': record_data.get('nickname'),
                        'firstname_eng': record_data.get('firstname_eng'),
                        'lastname_eng': record_data.get('lastname_eng'),
                        # ใช้ Many2one ID แทน
                        'branch_id': branch_id,
                        'marital_status': record_data.get('marital_status'),
                        'birthdate': record_data.get('birthdate'),
                        'age': record_data.get('age'),
                        'phone_number': record_data.get('phone_number'),
                        'email': record_data.get('email'),
                        'id_card_number': record_data.get('id_card_number'),
                        'passport_number': record_data.get('passport_number'),
                        'social_security_number': record_data.get('social_security_number'),
                        # ใช้ Many2one ID แทน
                        'position_id': position_id,
                        'department_id': department_id,
                        'company': record_data.get('company'),
                        'employee_type': record_data.get('employee_type'),
                        'salary': record_data.get('salary'),
                        'advance_payment_type': record_data.get('advance_payment_type'),
                        'advance_payment_limit': record_data.get('advance_payment_limit'),
                        'enable_social_security': record_data.get('enable_social_security'),
                        'social_security_condition': record_data.get('social_security_condition'),
                        'social_security_fixed_amount': record_data.get('social_security_fixed_amount'),
                        'social_security_start_date': record_data.get('social_security_start_date'),
                        'enable_tax': record_data.get('enable_tax'),
                        'tax_condition': record_data.get('tax_condition'),
                        'tax_exception': record_data.get('tax_exception'),
                        'tax_start_date_condition': record_data.get('tax_start_date_condition'),
                        'start_date': record_data.get('start_date'),
                        'appointment_date': record_data.get('appointment_date'),
                        'contract_end_date': record_data.get('contract_end_date'),
                        'end_trial_date': record_data.get('end_trial_date'),
                        'probation_period': record_data.get('probation_period'),
                        'retirement_year': record_data.get('retirement_year'),
                        'payment_channel': record_data.get('payment_channel'),
                        'payment_account_type': record_data.get('payment_account_type'),
                        'bank_name': record_data.get('bank_name'),
                        'bank_branch_code': record_data.get('bank_branch_code'),
                        'bank_account_number': record_data.get('bank_account_number'),
                        'details': record_data.get('details'),
                        'status': record_data.get('status'),
                        'cost_of_living': record_data.get('cost_of_living'),
                        'position_allowance': record_data.get('position_allowance'),
                        'experience_allowance': record_data.get('experience_allowance'),
                        'professional_allowance': record_data.get('professional_allowance'),
                    }

                    if existing_record:
                        existing_record.write(values)
                        _logger.info("Updated record for employee_code: %s", employee_code)
                    else:
                        self.create(values)
                        _logger.info("Created new record for employee_code: %s", employee_code)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Data imported successfully.',
                    'sticky': False,
                }
            }

        except requests.exceptions.RequestException as e:
            _logger.error("Failed to connect to the API: %s", e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Error',
                    'message': f"Failed to connect to the API: {e}",
                    'sticky': True,
                }
            }
        except Exception as e:
            _logger.error("An error occurred during import: %s", e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Error',
                    'message': f"An error occurred during import: {e}",
                    'sticky': True,
                }
            }
