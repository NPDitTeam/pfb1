import requests
import json
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, datetime
import base64
import logging

_logger = logging.getLogger(__name__)

LEAVE_API_URL = 'https://npdhrms.com/json_leave_requests.php'
LEAVE_UPDATE_URL = 'https://npdhrms.com/update_leave_request.php'
LEAVE_DELETE_URL = 'https://npdhrms.com/delete_leave_request.php'
API_USER = 'Npd_admin'
API_PASS = '78901234'
BASE_URL = 'https://npdhrms.com/'

# map: Odoo field -> SQL column (สำหรับ push กลับฝั่ง PHP ตอนแก้ไข)
# หมายเหตุ:
#   - คอลัมน์เวลาเริ่มต้นใน DB สะกดเป็น 'leave_statr_time' (typo ในฐานข้อมูลเดิม)
#   - ไม่ push 'branch' (GET ดึงจากตาราง users ไม่ใช่ leave_requests)
#   - ไม่ push 'approved_by' (DB เก็บเป็น id แต่ Odoo เก็บเป็นชื่อ จะทำให้ข้อมูลพัง)
SQL_FIELD_MAP = {
    'user_id': 'user_id',
    'username': 'username',
    'leave_start_date': 'leave_start_date',
    'start_time': 'leave_statr_time',
    'leave_end_date': 'leave_end_date',
    'end_time': 'leave_end_time',
    'leave_type': 'leave_type',
    'note': 'note',
    'state': 'state',
    'reason': 'reason',
    'department': 'department',
    'position': 'position',
    'file_path': 'file_path',
    'company': 'company',
}

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

LEAVE_TYPE_SELECTION = [
    ('ลากิจได้รับค่าจ้าง', 'ลากิจได้รับค่าจ้าง'),
    ('ลากิจไม่ได้รับค่าจ้าง', 'ลากิจไม่ได้รับค่าจ้าง'),
    ('ลาป่วยมีใบรับรองแพทย์', 'ลาป่วยมีใบรับรองแพทย์'),
    ('ลาคลอดได้รับค่าจ้าง', 'ลาคลอดได้รับค่าจ้าง'),
    ('ลาคลอดไม่ได้รับค่าจ้าง', 'ลาคลอดไม่ได้รับค่าจ้าง'),
    ('ลาพักร้อน', 'ลาพักร้อน'),
    ('สิทธิหยุดวันเสาร์', 'สิทธิหยุดวันเสาร์'),
    ('ฉุกเฉิน', 'ฉุกเฉิน'),
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


class LeaveRequest(models.Model):
    _name = 'hr.attendance.branch.leave'
    _description = 'การลา'

    hr_id_attendance_branch_leave = fields.Char(string="รหัสตาราง")
    user_id = fields.Char(string='รหัสพนักงาน (PHP)', required=True)
    employee_id = fields.Many2one('employee.salary', string='พนักงาน')

    # ดึงจาก employee.salary อัตโนมัติ
    branch_id = fields.Many2one(related='employee_id.branch_id', string='สาขา', store=True, readonly=True)
    department_id = fields.Many2one(related='employee_id.department_id', string='แผนก', store=True, readonly=True)
    position_id = fields.Many2one(related='employee_id.position_id', string='ตำแหน่ง', store=True, readonly=True)

    # field เดิม (ซ่อนไว้ เก็บค่าจาก API)
    branch = fields.Selection(selection=BRANCH_SELECTION, string='สาขา (เดิม)')
    department = fields.Selection(selection=DEPARTMENT_SELECTION, string='แผนก (เดิม)')
    position = fields.Selection(selection=POSITION_SELECTION, string='ตำแหน่ง (เดิม)')

    username = fields.Char(string='ชื่อผู้ใช้งาน', required=True)
    leave_start_date = fields.Date(string='วันที่ลาเริ่มต้น', required=True)
    start_time = fields.Char(string="เวลาที่ลาเริ่มต้น", required=True)
    leave_end_date = fields.Date(string='วันที่ลาสิ้นสุด', required=True)
    end_time = fields.Char(string="เวลาที่ลาสิ้นสุด", required=True)
    leave_type = fields.Selection(selection=LEAVE_TYPE_SELECTION, string='ประเภทการลา', required=True)
    note = fields.Text(string='หมายเหตุผู้ใช้')
    reason = fields.Char(string="หมายเหตุผู้อนุมัติ")
    state = fields.Selection(selection=TIME_STATES, string="สถานะ")
    file_path = fields.Char(string='ชื่อไฟล์แนบ')
    approved_by = fields.Char(string="ผู้อนุมัติ")
    date_requested = fields.Date(string='วันที่บันทึก', default=fields.Date.context_today)
    attachment = fields.Binary(string="ไฟล์แนบ")
    filename = fields.Char(string="ชื่อไฟล์")
    created_at = fields.Char(string='วันที่บันทึกข้อมูลการลา')
    file_link = fields.Char(string='ลิงก์ไฟล์แนบ', store=True)
    company = fields.Selection(selection=HRMS_COMPANY, string='บริษัท')

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

    # ---------------------------------------------------------------
    # Push กลับฝั่ง PHP/SQL (แก้ไข / ลบ)
    # ---------------------------------------------------------------
    def _push_update_to_api(self, payload):
        """ส่งข้อมูลที่แก้ไปอัพเดทตาราง leave_requests ฝั่ง SQL ผ่าน PHP"""
        try:
            resp = requests.post(
                LEAVE_UPDATE_URL,
                auth=(API_USER, API_PASS),
                json=payload,
                timeout=20,
            )
            resp.raise_for_status()
            result = resp.json()
            if not result.get('success'):
                raise UserError("อัพเดทข้อมูลฝั่ง SQL ไม่สำเร็จ: %s" % result.get('error'))
        except requests.exceptions.RequestException as e:
            raise UserError("เชื่อมต่อ API เพื่ออัพเดทข้อมูลไม่สำเร็จ: %s" % e)

    def _push_delete_to_api(self, sql_id):
        """ลบเรคคอร์ดในตาราง leave_requests ฝั่ง SQL ผ่าน PHP"""
        try:
            resp = requests.post(
                LEAVE_DELETE_URL,
                auth=(API_USER, API_PASS),
                json={'id': sql_id},
                timeout=20,
            )
            resp.raise_for_status()
            result = resp.json()
            if not result.get('success'):
                raise UserError("ลบข้อมูลฝั่ง SQL ไม่สำเร็จ: %s" % result.get('error'))
        except requests.exceptions.RequestException as e:
            raise UserError("เชื่อมต่อ API เพื่อลบข้อมูลไม่สำเร็จ: %s" % e)

    def write(self, vals):
        res = super(LeaveRequest, self).write(vals)
        # ข้ามถ้าเป็นการเขียนจาก cron sync (กันยิงกลับเป็นวงวน)
        if not self.env.context.get('skip_api_sync'):
            changed = [f for f in SQL_FIELD_MAP if f in vals]
            if changed:
                for rec in self:
                    if not rec.hr_id_attendance_branch_leave:
                        continue
                    payload = {'id': rec.hr_id_attendance_branch_leave}
                    for odoo_f in changed:
                        val = rec[odoo_f]
                        if isinstance(val, (date, datetime)):
                            val = fields.Date.to_string(val)
                        payload[SQL_FIELD_MAP[odoo_f]] = val if val not in (False, None) else None
                    rec._push_update_to_api(payload)
        return res

    def unlink(self):
        if not self.env.context.get('skip_api_sync'):
            # ลบฝั่ง SQL ก่อน ถ้าล้มเหลวจะ raise และไม่ลบฝั่ง Odoo (ให้ข้อมูลตรงกัน)
            for rec in self:
                if rec.hr_id_attendance_branch_leave:
                    rec._push_delete_to_api(rec.hr_id_attendance_branch_leave)
        return super(LeaveRequest, self).unlink()

    @api.model
    def sync_leave_requests_from_api(self):
        try:
            response = requests.get(LEAVE_API_URL, auth=(API_USER, API_PASS))
            response.raise_for_status()
            leave_records = json.loads(response.text)

            if not leave_records:
                raise UserError('ไม่พบข้อมูลการลาสำหรับวันนี้จาก API')

            for record in leave_records:
                existing_record = self.env['hr.attendance.branch.leave'].search([
                    ('hr_id_attendance_branch_leave', '=', str(record['id'])),
                ], limit=1)

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
                    'hr_id_attendance_branch_leave': str(record.get('id', False)),
                    'user_id': record.get('user_id'),
                    'employee_id': employee.id if employee else False,
                    'username': record.get('username'),
                    'leave_start_date': record.get('leave_start_date'),
                    'start_time': record.get('leave_start_time'),
                    'leave_end_date': record.get('leave_end_date'),
                    'end_time': record.get('leave_end_time'),
                    'leave_type': record.get('leave_type'),
                    'note': record.get('note'),
                    'state': record.get('state'),
                    'reason': record.get('reason'),
                    'approved_by': record.get('approved_by'),
                    'branch': branch_val,
                    'department': dept_val,
                    'position': pos_val,
                    'file_path': record.get('file_path'),
                    'created_at': record.get('created_at'),
                    'company': record.get('company'),
                }

                if record.get('file_path'):
                    try:
                        file_url = f"{BASE_URL}{record['file_path']}"
                        file_resp = requests.get(file_url, timeout=10)
                        if file_resp.status_code == 200:
                            data_to_write['attachment'] = base64.b64encode(file_resp.content).decode('utf-8')
                            data_to_write['filename'] = record['file_path'].split('/')[-1]
                    except Exception as e:
                        _logger.warning(f"โหลดไฟล์แนบไม่สำเร็จ: {e}")

                data_to_write = {k: v for k, v in data_to_write.items() if v}

                if existing_record:
                    existing_record.with_context(skip_api_sync=True).write(data_to_write)
                else:
                    self.env['hr.attendance.branch.leave'].with_context(skip_api_sync=True).create(data_to_write)

        except requests.exceptions.RequestException as e:
            raise UserError(f"มีข้อผิดพลาดในการเชื่อมต่อกับ API: {e}")
        except json.JSONDecodeError as e:
            raise UserError(f"มีข้อผิดพลาดในการถอดรหัส JSON: {e}")
        except Exception as e:
            raise UserError(f"มีข้อผิดพลาดในการนำเข้าข้อมูล: {e}")
