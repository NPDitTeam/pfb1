import requests
import json
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, datetime
import base64
import re
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

# ฟิลด์ที่พิมพ์อยู่บนใบลา — เปลี่ยนเมื่อไหร่ต้องออก PDF ใหม่
LEAVE_FORM_FIELDS = (
    'username', 'employee_id', 'position', 'branch', 'company',
    'leave_start_date', 'start_time', 'leave_end_date', 'end_time',
    'leave_type', 'note', 'state', 'reason', 'approved_by', 'approved_at',
    'created_at',
)

THAI_MONTHS = [
    'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
    'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม',
]

# ลาเกิน 8 ชม. ในวันเดียว (เช่น 08:00–17:00) นับเป็นลาทั้งวัน
HOURLY_LEAVE_MAX_MINUTES = 8 * 60

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
    # จอนี้แสดงวันเริ่ม/วันสิ้นสุดแยกคอลัมน์ ทำให้ใบที่ลาหลายวันดูเหมือนใบละ 1 วัน
    # (เคยนับ 5 ใบเป็น 5 วัน ทั้งที่เป็น 7 วัน) จึงโชว์จำนวนวันตรง ๆ ไปเลย
    # นับแบบเดียวกับที่ PHP หักยอดคงเหลือ: รวมวันเริ่มและวันสิ้นสุด
    leave_days = fields.Integer(
        string='จำนวนวันลา', compute='_compute_leave_days', store=True,
        help='นับรวมวันเริ่มและวันสิ้นสุด เช่น 25–27 = 3 วัน')
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
    approved_at = fields.Char(string='วันที่อนุมัติ')
    # ใบลา NPD/HR.03 ที่ระบบออกให้ (แอปเปิดดู/แชร์ไฟล์เดียวกันนี้)
    # สร้างใหม่ทุกครั้งที่ข้อมูลบนใบเปลี่ยน เช่น สถานะจาก cron sync
    leave_form_pdf = fields.Binary(string='ใบลา (PDF)', attachment=True, readonly=True)
    leave_form_filename = fields.Char(string='ชื่อไฟล์ใบลา', readonly=True)

    @api.depends('leave_start_date', 'leave_end_date')
    def _compute_leave_days(self):
        for rec in self:
            if rec.leave_start_date and rec.leave_end_date:
                rec.leave_days = max(
                    (rec.leave_end_date - rec.leave_start_date).days + 1, 1)
            else:
                rec.leave_days = 0

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
        # cron sync เขียนทุกฟิลด์ซ้ำทุก 15 นาที จึงต้องเทียบค่าจริง
        # ไม่งั้นจะสร้าง PDF ใหม่ทุกใบทุกรอบ
        form_fields = [f for f in LEAVE_FORM_FIELDS if f in vals]
        before = {rec.id: [rec[f] for f in form_fields] for rec in self} if form_fields else {}
        res = super(LeaveRequest, self).write(vals)
        if form_fields:
            stale = self.filtered(lambda r: [r[f] for f in form_fields] != before[r.id])
            stale._generate_leave_form_pdf()
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
                self._upsert_from_api_record(record)

        except requests.exceptions.RequestException as e:
            raise UserError(f"มีข้อผิดพลาดในการเชื่อมต่อกับ API: {e}")
        except json.JSONDecodeError as e:
            raise UserError(f"มีข้อผิดพลาดในการถอดรหัส JSON: {e}")
        except Exception as e:
            raise UserError(f"มีข้อผิดพลาดในการนำเข้าข้อมูล: {e}")

    @api.model
    def _upsert_from_api_record(self, record, always_fetch_attachment=True):
        """สร้าง/อัปเดตใบลา 1 ใบจากแถว leave_requests ฝั่ง PHP

        record ใช้รูปแบบเดียวกับ json_leave_requests.php
        (leave_start_time, approved_by = ชื่อผู้อนุมัติ) ทั้ง cron และแอปส่งมาแบบนี้
        """
        existing_record = self.search([
            ('hr_id_attendance_branch_leave', '=', str(record['id'])),
        ], limit=1)

        # หา employee: ลำดับ 1.employee_code จาก API 2.ชื่อ-นามสกุล
        employee = False
        emp_code = record.get('employee_code')
        username = record.get('username') or ''

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
        company_val = record.get('company') if record.get('company') in dict(HRMS_COMPANY) else False

        data_to_write = {
            'hr_id_attendance_branch_leave': str(record.get('id', False)),
            'user_id': record.get('user_id') and str(record['user_id']),
            'employee_id': employee.id if employee else False,
            'username': record.get('username'),
            'leave_start_date': record.get('leave_start_date'),
            'start_time': _normalize_time(record.get('leave_start_time')),
            'leave_end_date': record.get('leave_end_date'),
            'end_time': _normalize_time(record.get('leave_end_time')),
            'leave_type': record.get('leave_type'),
            'note': record.get('note'),
            'state': record.get('state'),
            'reason': record.get('reason'),
            'approved_by': record.get('approved_by'),
            'approved_at': record.get('approved_at'),
            'branch': branch_val,
            'department': dept_val,
            'position': pos_val,
            'file_path': record.get('file_path'),
            'created_at': record.get('created_at'),
            'company': company_val,
        }

        need_attachment = always_fetch_attachment or not existing_record.attachment
        if record.get('file_path') and need_attachment:
            try:
                file_url = f"{BASE_URL}{record['file_path']}"
                file_resp = requests.get(file_url, timeout=10)
                if file_resp.status_code == 200:
                    data_to_write['attachment'] = base64.b64encode(file_resp.content).decode('utf-8')
                    data_to_write['filename'] = record['file_path'].split('/')[-1]
            except Exception as e:
                _logger.warning(f"โหลดไฟล์แนบไม่สำเร็จ: {e}")

        data_to_write = {k: v for k, v in data_to_write.items() if v and v != 'NULL'}

        if existing_record:
            existing_record.with_context(skip_api_sync=True).write(data_to_write)
            return existing_record
        new_record = self.with_context(skip_api_sync=True).create(data_to_write)
        new_record._generate_leave_form_pdf()
        return new_record

    # ---------------------------------------------------------------
    # ใบลา NPD/HR.03 (PDF)
    # ---------------------------------------------------------------
    @api.model
    def api_leave_form_pdf(self, record):
        """สำหรับแอปมือถือ: คืนใบลา PDF ของคำขอลา 1 ใบ

        เรียกผ่าน JSON-RPC:
            callKw('hr.attendance.branch.leave', 'api_leave_form_pdf', [record])

        record = แถวจาก get_leave_history.php แปลงเป็นรูปแบบเดียวกับ
        json_leave_requests.php — อัปเดตข้อมูลเข้า Odoo ก่อน (ใบที่ยังรออนุมัติ
        ไม่ต้องรอ cron 15 นาที) แล้วคืนไฟล์ที่เก็บไว้บนเรคคอร์ด
        คืน {'id', 'filename', 'pdf' (base64)}
        """
        if not record or not record.get('id'):
            raise UserError('ไม่พบเลขที่คำขอลา')
        rec = self._upsert_from_api_record(record, always_fetch_attachment=False)
        if not rec.leave_form_pdf:
            rec._generate_leave_form_pdf()
        return {
            'id': rec.id,
            'filename': rec.leave_form_filename,
            'pdf': rec.leave_form_pdf.decode('ascii') if rec.leave_form_pdf else False,
        }

    def _generate_leave_form_pdf(self):
        """ออกใบลาใหม่แล้วเก็บไว้ที่ leave_form_pdf

        ห้ามทำให้งานหลักล้ม (cron sync / การบันทึก) — ออก PDF ไม่ได้ก็แค่ log ไว้
        แล้วรอบหน้าค่อยออกใหม่
        """
        report = self.env.ref('hr_attendance_branch.action_report_leave_form', raise_if_not_found=False)
        if not report:
            return
        for rec in self:
            try:
                pdf, _ = report.sudo()._render_qweb_pdf(rec.ids)
            except Exception as e:
                _logger.warning("ออกใบลา PDF ไม่สำเร็จ (id=%s): %s", rec.id, e)
                continue
            rec.with_context(skip_api_sync=True).write({
                'leave_form_pdf': base64.b64encode(pdf),
                'leave_form_filename': 'ใบลา_%s.pdf' % (rec.hr_id_attendance_branch_leave or rec.id),
            })

    def _leave_form_values(self):
        """ค่าที่พิมพ์ลงใบลา (ใช้ใน QWeb report_leave_form_document)"""
        self.ensure_one()

        def thai_date(d):
            if not d:
                return {'day': '', 'month': '', 'year': '', 'short': ''}
            return {
                'day': d.day,
                'month': THAI_MONTHS[d.month - 1],
                'year': d.year + 543,
                'short': '%02d/%02d/%d' % (d.day, d.month, d.year + 543),
            }

        def parse_date(value):
            if not value or value == 'NULL':
                return None
            try:
                return fields.Date.from_string(str(value)[:10])
            except Exception:
                return None

        def minutes(t):
            m = re.match(r'^(\d{1,2}):(\d{2})', t or '')
            return int(m.group(1)) * 60 + int(m.group(2)) if m else None

        emp = self.employee_id
        fullname = ('%s %s' % (emp.firstname or '', emp.lastname or '')).strip() if emp else ''
        company_key = (emp.company if emp else False) or self.company
        company_name = self.env['payroll.salary']._company_info_by_key(company_key)['name']
        branch_name = self.branch_id.name or self.branch or ''

        start_min, end_min = minutes(self.start_time), minutes(self.end_time)
        duration = (end_min - start_min) if start_min is not None and end_min is not None else None
        is_hourly = (self.leave_start_date == self.leave_end_date
                     and duration is not None and 0 < duration < HOURLY_LEAVE_MAX_MINUTES)

        leave_type = self.leave_type or ''

        if branch_name and branch_name != 'สำนักงานใหญ่':
            branch_name = 'สาขา' + branch_name
        created = parse_date(self.created_at) or self.date_requested
        return {
            'doc_no': self.hr_id_attendance_branch_leave or '',
            'written_at': ('%s %s' % (company_name, branch_name)).strip(),
            'created': thai_date(created),
            'fullname': fullname or self.username or '',
            'position': self.position_id.name or self.position or '',
            'leave_type': leave_type,
            'is_hourly': is_hourly,
            'start_time': (self.start_time or '')[:5],
            'end_time': (self.end_time or '')[:5],
            'hours': duration // 60 if is_hourly else '',
            'minutes': duration % 60 if is_hourly else '',
            'start': thai_date(self.leave_start_date),
            'end': thai_date(self.leave_end_date),
            'days': self.leave_days,
            # แถวประเภทการลาบนใบ = ประเภทเดียวกับในแอป
            # ค่าเก่าที่ไม่อยู่ในลิสต์แล้วต่อท้ายไว้ ไม่งั้นใบนั้นจะไม่มีช่องไหนถูกติ๊ก
            'type_rows': LEAVE_TYPE_SELECTION + (
                [(leave_type, leave_type)]
                if leave_type and leave_type not in dict(LEAVE_TYPE_SELECTION) else []),
            'note': self.note or '',
            'state': self.state or 'รออนุมัติ',
            'reason': self.reason or '',
            'approver': self.approved_by or '',
            'approved': thai_date(parse_date(self.approved_at)),
        }

    def action_regenerate_leave_form(self):
        self._generate_leave_form_pdf()


def _normalize_time(value):
    """'8:00' / '08:00' / '08:00:00' -> '08:00:00' (รูปแบบเดียวกับที่ cron เก็บไว้)

    แอปได้เวลาแบบ HH:mm ส่วน cron ได้ HH:mm:ss ถ้าไม่ทำให้ตรงกัน
    สองทางจะเขียนทับกันไปมาแล้วออก PDF ใหม่ทุกรอบ
    """
    m = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?', value or '')
    if not m:
        return value
    return '%02d:%s:%s' % (int(m.group(1)), m.group(2), m.group(3) or '00')
