import re
import requests
import json
from odoo import models, fields, api
from datetime import date
from odoo.exceptions import UserError

# ข้อมูลการเชื่อมต่อกับ PHP API
API_URL = 'https://npdhrms.com/json_checkin.php'
API_USER = 'Npd_admin'
API_PASS = '78901234'

BRANCH_SELECTION = [
    ("โคราช-บายพาส", "โคราช-บายพาส"),
    ("อุดรธานี", "อุดรธานี"),
    ("ขอนแก่น-โลตัส", "ขอนแก่น-โลตัส"),
    ("อุบลราชธานี", "อุบลราชธานี"),
    ("สุรินทร์", "สุรินทร์"),
    ("มหาสารคาม", "มหาสารคาม"),
    ("สำนักงานใหญ่", "สำนักงานใหญ่"),
    ("พัทยา", "พัทยา"),
    ("ปลวกแดง", "ปลวกแดง"),
    ("บ้านฉาง", "บ้านฉาง"),
    ("บางละมุง", "บางละมุง"),
    ("พิษณุโลก", "พิษณุโลก"),
    ("นครสวรรค์", "นครสวรรค์"),
    ("อรุณอมรินทร์", "อรุณอมรินทร์"),
    ("ปทุมธานี", "ปทุมธานี"),
    ("ชะอำ", "ชะอำ"),
    ("อยุธยา", "อยุธยา"),
    ("ทุ่งครุ", "ทุ่งครุ"),
    ("ภูเก็ต", "ภูเก็ต"),
    ("สุวินทวงศ์", "สุวินทวงศ์"),
    ("ลาดกระบัง", "ลาดกระบัง"),
    ("คลองหลวง", "คลองหลวง"),
    ("เชียงใหม่", "เชียงใหม่"),
    ("ศาลายา", "ศาลายา"),
    ("พระราม2", "พระราม2"),
    ("บ้านพลอย", "บ้านพลอย"),
    ("ลาดหลุมแก้ว", "ลาดหลุมแก้ว"),
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
    ("ไม่ระบุ", "ไม่ระบุ"),
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
    ("นภดลกรุงเทพจำกัด", "นภดลกรุงเทพจำกัด"),
    ("นภดลอินเตอร์เทรดดิ้งจำกัด", "นภดลอินเตอร์เทรดดิ้งจำกัด"),
    ("ไม่ระบุบริษัท", "ไม่ระบุบริษัท"),
]


class AttendanceRecord(models.Model):
    _name = 'hr.attendance.branch'
    _description = 'เข้างานออกงาน'

    # เพิ่ม SQL Constraint ป้องกันข้อมูลซ้ำ
    _sql_constraints = [
        ('unique_attendance',
         'UNIQUE(user_id, checked_at, check_type)',
         'ข้อมูลการลงเวลาซ้ำ! (user_id, checked_at, check_type ต้องไม่ซ้ำกัน)')
    ]

    user_id = fields.Char(string='รหัสพนักงาน (PHP)', required=True)
    employee_id = fields.Many2one('employee.salary', string='พนักงาน')
    username = fields.Char(string='ชื่อผู้ใช้งาน', required=True)

    # ดึงจาก employee.salary อัตโนมัติ
    branch_id = fields.Many2one(related='employee_id.branch_id', string='สาขา', store=True, readonly=True)
    department_id = fields.Many2one(related='employee_id.department_id', string='แผนก', store=True, readonly=True)
    position_id = fields.Many2one(related='employee_id.position_id', string='ตำแหน่ง', store=True, readonly=True)

    # field เดิม (ซ่อนไว้ เก็บค่าจาก API)
    branch = fields.Selection(selection=BRANCH_SELECTION, string='สาขา (เดิม)')
    department = fields.Selection(selection=DEPARTMENT_SELECTION, string='แผนก (เดิม)')
    position = fields.Selection(selection=POSITION_SELECTION, string='ตำแหน่ง (เดิม)')

    check_type = fields.Selection([('in', 'เข้า'), ('out', 'ออก')], string='ประเภทการลงเวลา', required=True)
    latitude = fields.Char(string='ละติจูด')
    longitude = fields.Char(string='ลองจิจูด')
    checked_at = fields.Char(string='ลงเวลาเมื่อ')
    date_requested = fields.Date(string='วันที่บันทึก', default=fields.Date.context_today)
    company = fields.Selection(selection=HRMS_COMPANY, string='บริษัท')
    address = fields.Char(string='ที่อยู่ (GPS)')
    accuracy = fields.Float(string='ความแม่นยำ (เมตร)', digits=(8, 2))

    def _get_department_by_name(self, name):
        """ค้นหา department_id จากชื่อ"""
        if not name:
            return False
        department = self.env['hr.department.custom'].search([('name', '=', name)], limit=1)
        if not department:
            department = self.env['hr.department.custom'].with_context(skip_api_sync=True).create({
                'name': name,
                'is_active': True
            })
        return department.id

    def _get_position_by_name(self, name):
        """ค้นหา position_id จากชื่อ"""
        if not name:
            return False
        position = self.env['hr.position.custom'].search([('name', '=', name)], limit=1)
        if not position:
            position = self.env['hr.position.custom'].with_context(skip_api_sync=True).create({
                'name': name,
                'is_active': True
            })
        return position.id

    def _get_branch_by_name(self, name):
        """ค้นหา branch_id จากชื่อ"""
        if not name:
            return False
        branch = self.env['hr.branch.custom'].search([('name', '=', name)], limit=1)
        if not branch:
            branch = self.env['hr.branch.custom'].with_context(skip_api_sync=True).create({
                'name': name
            })
        return branch.id

    @staticmethod
    def _clean_address(addr):
        """คลีน address ที่ได้จาก reverse geocoding
        - ตัด Plus Code (เช่น '3J8Q+3CR ')
        - แก้ 'ต.ตำบล X' → 'ต.X', 'อ.อำเภอ X' → 'อ.X', 'จ.จังหวัด X' → 'จ.X'
        - ลบ space ซ้ำ
        """
        if not addr:
            return addr
        s = str(addr)
        # ตัด Plus Code ที่ขึ้นต้น (รูปแบบ XXXX+XXX หรือ XXXX+XX)
        s = re.sub(r'^\s*[A-Z0-9]{4,}\+[A-Z0-9]{2,4}\s*', '', s)
        # แก้คำซ้ำซ้อน
        s = re.sub(r'ต\.\s*ตำบล\s*', 'ต.', s)
        s = re.sub(r'อ\.\s*อำเภอ\s*', 'อ.', s)
        s = re.sub(r'จ\.\s*จังหวัด\s*', 'จ.', s)
        s = re.sub(r'แขวง\s*แขวง\s*', 'แขวง', s)
        s = re.sub(r'เขต\s*เขต\s*', 'เขต', s)
        # ลบ space ซ้ำ
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    @api.model
    def sync_checkin_logs_from_api(self, date_from=None, date_to=None, target_date=None):
        """ดึงข้อมูลการลงเวลาจาก PHP API และนำเข้าสู่ Odoo
        - ไม่ส่ง parameter = วันนี้
        - target_date='2026-04-06' = วันเดียว
        - date_from + date_to = ช่วงวัน
        """
        try:
            params = {}
            if date_from and date_to:
                params = {'date_from': date_from, 'date_to': date_to}
            elif target_date:
                params = {'date': target_date}

            response = requests.get(API_URL, auth=(API_USER, API_PASS), params=params)
            response.raise_for_status()
            checkin_records = json.loads(response.text)

            if not checkin_records:
                raise UserError('ไม่พบข้อมูลการลงเวลาสำหรับวันนี้จาก API')

            for record in checkin_records:
                existing_record = self.env['hr.attendance.branch'].search([
                    ('user_id', '=', record['user_id']),
                    ('checked_at', '=', record['checked_at']),
                    ('check_type', '=', record['check_type']),  # เพิ่มเงื่อนไข check_type
                ], limit=1)

                if not existing_record:
                    # หา employee: ลำดับ 1.employee_code จาก API 2.ชื่อ-นามสกุล
                    employee = False
                    emp_code = record.get('employee_code')
                    username = record.get('username', '')

                    # ลำดับ 1: match จาก employee_code ที่ PHP ส่งมา
                    if emp_code:
                        employee = self.env['employee.salary'].sudo().search(
                            [('employee_code', '=', str(emp_code))], limit=1
                        )

                    # ลำดับ 2: match จากชื่อ-นามสกุล
                    if not employee and username:
                        parts = username.strip().split(' ', 1)
                        if len(parts) == 2:
                            employee = self.env['employee.salary'].sudo().search([
                                ('firstname', '=', parts[0]),
                                ('lastname', '=', parts[1]),
                            ], limit=1)

                    # เขียน field Selection เดิมเฉพาะค่าที่อยู่ในลิสต์
                    branch_val = record.get('branch') if record.get('branch') in dict(BRANCH_SELECTION) else False
                    dept_val = record.get('department') if record.get('department') in dict(DEPARTMENT_SELECTION) else False
                    pos_val = record.get('position') if record.get('position') in dict(POSITION_SELECTION) else False

                    self.env['hr.attendance.branch'].create({
                        'user_id': record['user_id'],
                        'employee_id': employee.id if employee else False,
                        'username': record['username'],
                        'branch': branch_val,
                        'department': dept_val,
                        'position': pos_val,
                        'check_type': record['check_type'],
                        'latitude': record['latitude'],
                        'longitude': record['longitude'],
                        'checked_at': record['checked_at'],
                        'date_requested': record['date_requested'],
                        'company': record['company'],
                        'address': self._clean_address(record.get('address')),
                        'accuracy': float(record['accuracy']) if record.get('accuracy') not in (None, '', False) else 0.0,
                    })
                else:
                    # backfill address/accuracy ให้ record เดิมที่ยังไม่มีค่า
                    update_vals = {}
                    if not existing_record.address and record.get('address'):
                        update_vals['address'] = self._clean_address(record.get('address'))
                    if not existing_record.accuracy and record.get('accuracy') not in (None, '', False):
                        update_vals['accuracy'] = float(record['accuracy'])
                    if update_vals:
                        existing_record.write(update_vals)

        except requests.exceptions.RequestException as e:
            raise UserError(f"มีข้อผิดพลาดในการเชื่อมต่อกับ API: {e}")
        except json.JSONDecodeError as e:
            raise UserError(f"มีข้อผิดพลาดในการถอดรหัส JSON: {e}")
        except Exception as e:
            raise UserError(f"มีข้อผิดพลาดในการนำเข้าข้อมูล: {e}")
