import requests
import json
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date

MANUAL_API_URL = 'https://npdhrms.com/json_manual_time_logs.php'
API_USER = 'Npd_admin'
API_PASS = '78901234'
FILE_BASE_URL = 'https://npdhrms.com/api/'

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

TIME_STATES = [
    ("รออนุมัติ", "รออนุมัติ"),
    ("อนุมัติ", "อนุมัติ"),
    ("ไม่อนุมัติ", "ไม่อนุมัติ"),
    ("ยกเลิก", "ยกเลิก"),
]

HRMS_COMPANY = [
    ("นภดลเอสกรุ๊ปจำกัด", "นภดลเอสกรุ๊ปจำกัด"),
    ("เอ็นพีดีสตีลเทคจำกัด", "เอ็นพีดีสตีลเทคจำกัด"),
    ("เอ็นพีดีโลจิสติกส์จำกัด", "เอ็นพีดีโลจิสติกส์จำกัด"),
    ("นภดลกรุงเทพจำกัด", "นภดลกรุงเทพจำกัด"),
    ("นภดลอินเตอร์เทรดดิ้งจำกัด", "นภดลอินเตอร์เทรดดิ้งจำกัด"),
    ("ไม่ระบุบริษัท", "ไม่ระบุบริษัท"),
]

REASON_TYPE = [
    ("ทำงานนอกสถานที่", "ทำงานนอกสถานที่"),
    ("ระบบมีปัญหา", "ระบบมีปัญหา"),
    ("ลืมลงเวลา", "ลืมลงเวลา"),
    ("ขอโอที", "ขอโอที"),
    ("ค่าเบี้ยเลี้ยงออกนอกสถานที่", "ค่าเบี้ยเลี้ยงออกนอกสถานที่"),
    ("ค่ารักษาพยาบาล", "ค่ารักษาพยาบาล"),
    ("ค่าอาหาร", "ค่าอาหาร"),
    ("ไม่ระบุ", "ไม่ระบุ"),
]


class ManualTimeLog(models.Model):
    _name = 'hr.manual.time.log'
    _description = 'เพิ่มเวลา'
    _order = 'work_date desc'

    hr_id_manual_time_log = fields.Char(string="รหัสตาราง")
    user_id = fields.Char(string="รหัสพนักงาน (PHP)", required=True)
    employee_id = fields.Many2one('employee.salary', string='พนักงาน')

    # ดึงจาก employee.salary อัตโนมัติ
    branch_id = fields.Many2one(related='employee_id.branch_id', string='สาขา', store=True, readonly=True)
    department_id = fields.Many2one(related='employee_id.department_id', string='แผนก', store=True, readonly=True)
    position_id = fields.Many2one(related='employee_id.position_id', string='ตำแหน่ง', store=True, readonly=True)

    # field เดิม (ซ่อนไว้ เก็บค่าจาก API)
    branch = fields.Selection(selection=BRANCH_SELECTION, string='สาขา (เดิม)')
    department = fields.Selection(selection=DEPARTMENT_SELECTION, string='แผนก (เดิม)')
    position = fields.Selection(selection=POSITION_SELECTION, string='ตำแหน่ง (เดิม)')

    username = fields.Char(string="ชื่อผู้ใช้งาน", required=True)
    work_date = fields.Date(string="วันที่ทำงาน", required=True)
    checkin_time = fields.Char(string="เวลาเข้างาน", required=True)
    checkout_time = fields.Char(string="เวลาออกงาน", required=True)
    state = fields.Selection(selection=TIME_STATES, string="สถานะ")
    user_note = fields.Char(string="หมายเหตุผู้ใช้")
    reason = fields.Char(string="หมายเหตุผู้อนุมัติ")
    approved_by = fields.Char(string="ผู้อนุมัติ")
    date_requested = fields.Date(string='วันที่บันทึก', default=fields.Date.context_today)
    company = fields.Selection(selection=HRMS_COMPANY, string='บริษัท')
    file_url = fields.Char(string="ไฟล์แนบ")
    reason_type = fields.Selection(selection=REASON_TYPE, string='ประเภทการเพิ่มเวลา')
    allowance_type = fields.Char(string='รายการประเภทค่าเบี้ยเลี้ยง')
    amount = fields.Float(string='จำนวนเงิน (บาท)')
    file_link = fields.Html(string="ดูไฟล์", compute="_compute_file_link", sanitize=False)

    @api.depends('file_url')
    def _compute_file_link(self):
        for rec in self:
            if rec.file_url:
                rec.file_link = f'<a href="{rec.file_url}" target="_blank">📎 เปิดไฟล์</a>'
            else:
                rec.file_link = "-"

    def _get_department_by_name(self, name):
        if not name:
            return False
        department = self.env['hr.department.custom'].search([('name', '=', name)], limit=1)
        if not department:
            department = self.env['hr.department.custom'].with_context(skip_api_sync=True).create({
                'name': name, 'is_active': True
            })
        return department.id

    def _get_position_by_name(self, name):
        if not name:
            return False
        position = self.env['hr.position.custom'].search([('name', '=', name)], limit=1)
        if not position:
            position = self.env['hr.position.custom'].with_context(skip_api_sync=True).create({
                'name': name, 'is_active': True
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

    @api.model
    def sync_manual_time_logs_from_api(self):
        try:
            response = requests.get(MANUAL_API_URL, auth=(API_USER, API_PASS))
            response.raise_for_status()
            manual_records = json.loads(response.text)

            if not manual_records:
                raise UserError('ไม่พบข้อมูลบันทึกเวลาด้วยตนเองสำหรับวันนี้จาก API')

            for record in manual_records:
                existing_record = self.env['hr.manual.time.log'].search([
                    ('user_id', '=', record['user_id']),
                    ('work_date', '=', record['work_date']),
                    ('checkin_time', '=', record['checkin_time']),
                ], limit=1)

                file_url = None
                if record.get('file_path'):
                    file_url = FILE_BASE_URL + record['file_path']

                # หา employee: ลำดับ 1.employee_code จาก API 2.ชื่อ-นามสกุล
                employee = False
                emp_code = record.get('employee_code')
                username = record.get('username', '')

                if emp_code:
                    employee = self.env['employee.salary'].sudo().search(
                        [('employee_code', '=', str(emp_code))], limit=1
                    )

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

                data_to_write = {
                    'hr_id_manual_time_log': record['hr_id_manual_time_log'],
                    'username': record['username'],
                    'employee_id': employee.id if employee else False,
                    'branch': branch_val,
                    'department': dept_val,
                    'position': pos_val,
                    'checkin_time': record['checkin_time'],
                    'checkout_time': record['checkout_time'],
                    'state': record['state'],
                    'user_note': record['user_note'],
                    'work_date': record['work_date'],
                    'approved_by': record['approved_by'],
                    'reason': record['reason'],
                    'company': record['company'],
                    'reason_type': record.get('reason_type') or 'ไม่ระบุ',
                    'allowance_type': record.get('allowance_type') or False,
                    'amount': float(record.get('amount', 0) or 0),
                    'file_url': file_url
                }

                if existing_record:
                    existing_record.write(data_to_write)
                else:
                    data_to_write.update({
                        'user_id': record['user_id'],
                        'work_date': record['work_date'],
                        'checkin_time': record['checkin_time'],
                    })
                    self.env['hr.manual.time.log'].create(data_to_write)

        except requests.exceptions.RequestException as e:
            raise UserError(f"มีข้อผิดพลาดในการเชื่อมต่อกับ API: {e}")
        except json.JSONDecodeError as e:
            raise UserError(f"มีข้อผิดพลาดในการถอดรหัส JSON: {e}")
        except Exception as e:
            raise UserError(f"มีข้อผิดพลาดในการนำเข้าข้อมูล: {e}")
