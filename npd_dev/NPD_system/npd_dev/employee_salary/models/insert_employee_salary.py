# -*- coding: utf-8 -*-
import requests
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

# Add a configuration variable for the API endpoint URL
API_URL = "https://npdhrms.com/export_data.php"


class EmployeeSalary(models.Model):
    _name = 'employee.salary'
    _description = 'Employee Salary'
    _rec_name = 'firstname'

    _sql_constraints = [
        ('employee_code_uniq', 'unique(employee_code)', 'ไม่สามารถเพิ่มข้อมูลพนักงานซ้ำได้!')
    ]

    DEPARTMENT_SELECTION = [
        ("ก่อสร้าง", "ก่อสร้าง"),
        ("การตลาด", "การตลาด"),
        ("การเงิน", "การเงิน"),
        ("ขนส่ง", "ขนส่ง"),
        ("ขาย", "ขาย"),
        ("คลังสินค้า", "คลังสินค้า"),
        ("จัดซื้อ", "จัดซื้อ"),
        ("บริหาร", "บริหาร"),
        ("บัญชี", "บัญชี"),
        ("บุคคล", "บุคคล"),
        ("ผลิต", "ผลิต"),
        ("ยกสินค้า", "ยกสินค้า"),
        ("สต๊อก", "สต๊อก"),
        ("เช่า", "เช่า"),
        ("เร่งรัด/กฎหมาย", "เร่งรัด/กฎหมาย"),
        ("ไอที", "ไอที"),
    ]

    POSITION_SELECTION = [
        ("เจ้าหน้าที่ กราฟฟิค", "เจ้าหน้าที่ กราฟฟิค"),
        ("เจ้าหน้าที่ การเงิน", "เจ้าหน้าที่ การเงิน"),
        ("เจ้าหน้าที่ การตลาด", "เจ้าหน้าที่ การตลาด"),
        ("เจ้าหน้าที่ รับยอดสินค้า", "เจ้าหน้าที่ รับยอดสินค้า"),
        ("เจ้าหน้าที่ ขาย", "เจ้าหน้าที่ ขาย"),
        ("เจ้าหน้าที่คลังสินค้า", "เจ้าหน้าที่คลังสินค้า"),
        ("เจ้าหน้าที่ จัดซื้อ", "เจ้าหน้าที่ จัดซื้อ"),
        ("เจ้าหน้าที่ ซ่อมบำรุง", "เจ้าหน้าที่ ซ่อมบำรุง"),
        ("เจ้าหน้าที่ ธุรการ/ประสานงาน", "เจ้าหน้าที่ ธุรการ/ประสานงาน"),
        ("เจ้าหน้าที่ บิลลิ่ง", "เจ้าหน้าที่ บิลลิ่ง"),
        ("เจ้าหน้าที่ บัญชี", "เจ้าหน้าที่ บัญชี"),
        ("เจ้าหน้าที่ บุคคล", "เจ้าหน้าที่ บุคคล"),
        ("เจ้าหน้าที่ โปรแกรมเมอร์", "เจ้าหน้าที่ โปรแกรมเมอร์"),
        ("เจ้าหน้าที่ ผลิตสินค้า", "เจ้าหน้าที่ ผลิตสินค้า"),
        ("เจ้าหน้าที่ ฝ่ายผลิต", "เจ้าหน้าที่ ฝ่ายผลิต"),
        ("เจ้าหน้าที่ ยกสินค้า", "เจ้าหน้าที่ ยกสินค้า"),
        ("พนักงาน ยกสินค้า", "พนักงาน ยกสินค้า"),
        ("เจ้าหน้าที่ เร่งรัดหนี้สิน", "เจ้าหน้าที่ เร่งรัดหนี้สิน"),
        ("เจ้าหน้าที่ ออกแบบ", "เจ้าหน้าที่ ออกแบบ"),
        ("เจ้าหน้าที่ ไอทีซัพพอร์ต", "เจ้าหน้าที่ ไอทีซัพพอร์ต"),
        ("เจ้าหน้าที่ Admin", "เจ้าหน้าที่ Admin"),
        ("เจ้าหน้าที่ PC/คลังสินค้า", "เจ้าหน้าที่ PC/คลังสินค้า"),
        ("เจ้าหน้าที่ PC/บัญชี", "เจ้าหน้าที่ PC/บัญชี"),
        ("ผู้จัดการ", "ผู้จัดการ"),
        ("แม่บ้าน", "แม่บ้าน"),
        ("หัวหน้าสาขา", "หัวหน้าสาขา"),
        ("Lead Generation", "Lead Generation"),
        ("ที่ปรึกษา", "ที่ปรึกษา"),
        ("เจ้าหน้าที่ ขับรถขนสินค้า", "เจ้าหน้าที่ ขับรถขนสินค้า"),
        ("ไม่ระบุ", "ไม่ระบุ"),
        ("หัวหน้าฝ่าย", "หัวหน้าฝ่าย"),
        ("หัวหน้าแผนก", "หัวหน้าแผนก"),
        ("เจ้าหน้าที่ นิติกร", "เจ้าหน้าที่ นิติกร"),
    ]

    HRMS_COMPANY = [
        ("นภดลเอสกรุ๊ปจำกัด", "นภดลเอสกรุ๊ปจำกัด"),
        ("เอ็นพีดีสตีลเทคจำกัด", "เอ็นพีดีสตีลเทคจำกัด"),
        ("เอ็นพีดีโลจิสติกส์จำกัด", "เอ็นพีดีโลจิสติกส์จำกัด"),
        ("นภดลอินเตอร์เทรดดิ้งจำกัด", "นภดลอินเตอร์เทรดดิ้งจำกัด"),
    ]

    employee_code = fields.Char(string='รหัสพนักงาน')
    fingerprint_id = fields.Char(string='รหัสลายนิ้วมือ')
    pin = fields.Char(string='PIN 6 หลัก')
    prefix_th = fields.Selection([('นาย', 'นาย'), ('นางสาว', 'นางสาว'), ('นาง', 'นาง')], string='คำนำหน้าชื่อ')
    nationality = fields.Selection([('ไทย', 'ไทย'), ('ต่างชาติ', 'ต่างชาติ')], string='สัญชาติ')
    allow_offsite_time = fields.Boolean(string='อนุญาตลงเวลานอกสถานที่')
    gender = fields.Selection([('ชาย', 'ชาย'), ('หญิง', 'หญิง')], string='เพศ')

    # Personal Information
    firstname = fields.Char(string='ชื่อ')
    lastname = fields.Char(string='นามสกุล')
    nickname = fields.Char(string='ชื่อเล่น')
    firstname_eng = fields.Char(string='ชื่อ (ENG)')
    lastname_eng = fields.Char(string='นามสกุล (ENG)')
    branch = fields.Char(string='สาขา')
    marital_status = fields.Selection([('โสด', 'โสด'), ('สมรส', 'สมรส'), ('หย่า', 'หย่า')], string='สถานะ')
    birthdate = fields.Date(string='วันเกิด')
    age = fields.Integer(string='อายุ')
    phone_number = fields.Char(string='เบอร์โทรศัพท์')
    email = fields.Char(string='อีเมล')
    id_card_number = fields.Char(string='เลขประจำตัวประชาชน')
    passport_number = fields.Char(string='เลขที่หนังสือเดินทาง')
    social_security_number = fields.Char(string='ประกันสังคม')
    position = fields.Selection(selection=POSITION_SELECTION, string='ตำแหน่ง')
    department = fields.Selection(selection=DEPARTMENT_SELECTION, string='แผนก')
    company = fields.Selection(selection=HRMS_COMPANY, string='บริษัท')
    employee_type = fields.Selection([('ประจำ', 'ประจำ'), ('ทดลองงาน', 'ทดลองงาน'), ('รายวัน', 'รายวัน')],
                                     string='ประเภทพนักงาน')
    salary = fields.Float(string='ค่าจ้าง')
    advance_payment_type = fields.Selection([('ค่าเดินทาง', 'ค่าเดินทาง'), ('ค่าเบี้ยเลี้ยง', 'ค่าเบี้ยเลี้ยง')],
                                            string='เงินเบิกล่วงหน้า')
    advance_payment_limit = fields.Float(string='วงเงินเบิกล่วงหน้า')

    # Financial Information
    enable_social_security = fields.Boolean(string='ประกันสังคม', default=True)
    social_security_condition = fields.Selection(
        [('คิดตามฐานเงินเดือนจริงที่ได้รับ', 'คิดตามฐานเงินเดือนจริงที่ได้รับ')], string='เงื่อนไขประกันสังคม')
    social_security_fixed_amount = fields.Float(string='ค่าคงที่ของประกันสังคม')
    social_security_start_date = fields.Date(string='เงื่อนไขที่เริ่มคำนวณประกันสังคม')
    enable_tax = fields.Boolean(string='ภาษี', default=True)
    tax_condition = fields.Selection([('คิดภาษี ภงด.1 ใหม่ทุกเดือน', 'คิดภาษี ภงด.1 ใหม่ทุกเดือน')],
                                     string='เงื่อนไขภาษี')
    tax_exception = fields.Float(string='จำนวนภาษีคงที่ต่อเดือน')
    tax_start_date_condition = fields.Date(string='เงื่อนไขที่เริ่มคำนวณภาษี')

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
    device_id = fields.Char(string='Device ID')

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
        default='active'  # 👈 กำหนดค่าเริ่มต้น
    )

    def _sync_to_api(self, action, values=None):
        """
        เมธอดสำหรับส่งข้อมูลไปยัง PHP API Endpoint สำหรับการดำเนินการ CRUD
        """
        for rec in self:
            try:
                if action == 'delete':
                    payload = {'action': action, 'id': rec.id}
                elif action == 'create':
                    payload = {'action': action}
                    all_fields = rec.read()[0]
                    # ใช้ `all_fields` เพื่อให้รวมข้อมูลทุกฟิลด์
                    payload.update(all_fields)
                    # ลบฟิลด์ที่ไม่จำเป็น เช่น id จากการสร้างใหม่
                    payload.pop('id')
                else:  # action == 'update'
                    payload = {'action': action, 'id': rec.id}
                    # ใช้เฉพาะค่าที่ถูกแก้ไข
                    payload.update(values)

                response = requests.post(API_URL, json=payload)
                response.raise_for_status()

                api_response = response.json()
                if api_response.get('status') == 'success':
                    _logger.info("Successfully synced to API for record ID %s with action: %s", rec.id, action)
                else:
                    _logger.error("API sync failed for record ID %s. Message: %s", rec.id, api_response.get('message'))

            except requests.exceptions.RequestException as e:
                _logger.error("Failed to connect to API for record ID %s: %s", rec.id, e)
            except Exception as e:
                _logger.error("An unexpected error occurred during API sync for record ID %s: %s", rec.id, e)

    @api.model
    def create(self, vals):
        record = super(EmployeeSalary, self).create(vals)
        record._sync_to_api('create')
        return record

    def write(self, vals):
        res = super(EmployeeSalary, self).write(vals)
        if res:
            self._sync_to_api('update', values=vals)
        return res

    # def unlink(self):
    #     # unlink() ต้องถูกเรียกก่อน super() เพื่อให้สามารถอ่านค่า ID ได้
    #     for rec in self:
    #         rec._sync_to_api('delete')
    #     return super(EmployeeSalary, self).unlink()

    def import_from_php(self):
        try:
            # Fetch data from the PHP endpoint
            _logger.info("Attempting to fetch data from API: %s", API_URL)
            response = requests.get(API_URL)
            response.raise_for_status()

            # Parse the JSON response
            data = response.json()
            _logger.info("Data successfully fetched. Status: %s", data.get('status'))

            if data.get('status') != 'success' or not isinstance(data.get('data'), list):
                _logger.error("Invalid data format from API: %s", data)
                raise Exception("Invalid data received from the API.")

            for record_data in data['data']:
                employee_code = record_data.get('employee_code')

                if employee_code:
                    existing_record = self.search([('employee_code', '=', employee_code)], limit=1)

                    # Correctly map the fields to their respective data types.
                    values = {
                        'employee_code': record_data.get('employee_code'),
                        'fingerprint_id': record_data.get('fingerprint_id'),
                        'pin': record_data.get('password'),
                        'prefix_th': record_data.get('prefix_th'),
                        'nationality': record_data.get('nationality'),
                        'allow_offsite_time': record_data.get('allow_offsite_time'),
                        'gender': record_data.get('gender'),
                        'firstname': record_data.get('firstname'),
                        'lastname': record_data.get('lastname'),
                        'nickname': record_data.get('nickname'),
                        'firstname_eng': record_data.get('firstname_eng'),
                        'lastname_eng': record_data.get('lastname_eng'),
                        'branch': record_data.get('branch'),
                        'marital_status': record_data.get('marital_status'),
                        'birthdate': record_data.get('birthdate'),
                        'age': record_data.get('age'),
                        'phone_number': record_data.get('phone_number'),
                        'email': record_data.get('email'),
                        'id_card_number': record_data.get('id_card_number'),
                        'passport_number': record_data.get('passport_number'),
                        'social_security_number': record_data.get('social_security_number'),
                        'position': record_data.get('position'),
                        'department': record_data.get('department'),
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
                        'device_id': record_data.get('device_id'),
                        'status': record_data.get('status'),

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

