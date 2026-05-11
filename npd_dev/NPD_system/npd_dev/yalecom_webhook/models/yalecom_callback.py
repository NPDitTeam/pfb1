# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)


class YalecomCallLog(models.Model):
    """บันทึกประวัติการโทรจาก Yalecom (Read Only)"""
    _name = 'yalecom.call.log'
    _description = 'Yalecom Call Log'
    _order = 'call_time desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('ชื่อรายการ', compute='_compute_name', store=True)
    
    # ==================== ข้อมูลหลักจาก Yalecom ====================
    
    # Unique ID
    xml_cdr_uuid = fields.Char('XML CDR UUID', index=True, tracking=True, 
                               help='Unique ID ของสาย')
    call_id = fields.Char('Call ID', index=True, tracking=True,
                          help='Call ID (ใช้ xml_cdr_uuid)')
    
    # ข้อมูลผู้โทร
    caller_id_name = fields.Char('ชื่อผู้โทร', tracking=True,
                                  help='ชื่อของผู้โทร')
    caller_id_number = fields.Char('เบอร์ผู้โทร', tracking=True,
                                    help='เบอร์ของผู้โทร')
    source_number = fields.Char('เบอร์ต้นทาง', 
                                help='เบอร์ของผู้โทร (กรณีเบอร์ของผู้โทรมีอีกค่า)')
    
    # ข้อมูลปลายทาง
    caller_destination = fields.Char('จุดหมายหลัก', tracking=True,
                                      help='จุดหมายหลักของสาย (โดยปกติจะเป็นเบอร์ภายนอก)')
    last_destination = fields.Char('จุดหมายสุดท้าย',
                                   help='จุดหมายสุดท้าย')
    
    # ข้อมูลการวางสาย
    sip_hangup_disposition = fields.Selection([
        ('caller', 'ผู้โทรวางสาย'),
        ('callee', 'ผู้รับวางสาย'),
    ], string='ผู้วางสาย', help='ระบุว่าใครเป็นผู้วางสาย')
    
    # เวลา
    start_stamp = fields.Datetime('เวลาเริ่มต้นสาย', tracking=True,
                                   help='เวลาเริ่มต้นของสาย')
    end_stamp = fields.Datetime('เวลาจบสาย',
                                help='เวลาจบของสาย')
    
    # เวลาแสดงรูปแบบไทย (UTC+7)
    start_stamp_thai = fields.Char('เวลาเริ่มสาย (ไทย)', compute='_compute_thai_datetime', store=True,
                                    help='เวลาเริ่มต้นสายในรูปแบบไทย (วว/ดด/ปปปป ชช:นน:วว)')
    end_stamp_thai = fields.Char('เวลาจบสาย (ไทย)', compute='_compute_thai_datetime', store=True,
                                  help='เวลาจบสายในรูปแบบไทย (วว/ดด/ปปปป ชช:นน:วว)')
    start_date_thai = fields.Char('วันที่เริ่มสาย (ไทย)', compute='_compute_thai_datetime', store=True,
                                   help='วันที่เริ่มต้นสายในรูปแบบไทย (วว/ดด/ปปปป)')
    start_time_thai = fields.Char('เวลาเริ่มสาย (ไทย)', compute='_compute_thai_datetime', store=True,
                                   help='เวลาเริ่มต้นสายในรูปแบบไทย (ชช:นน:วว)')
    
    # เวลาแสดงรูปแบบ UTC (เก็บเป็น Char เพื่อไม่ให้ Odoo แปลง timezone)
    start_stamp_utc = fields.Char('เวลาเริ่มสาย (UTC)', compute='_compute_thai_datetime', store=True,
                                   help='เวลาเริ่มต้นสายในรูปแบบ UTC (วว/ดด/ปปปป ชช:นน:วว)')
    end_stamp_utc = fields.Char('เวลาจบสาย (UTC)', compute='_compute_thai_datetime', store=True,
                                 help='เวลาจบสายในรูปแบบ UTC (วว/ดด/ปปปป ชช:นน:วว)')
    
    # แผนกจากจุดหมายสุดท้าย
    department_code = fields.Selection([
        ('101', 'เช่าขาย'),
        ('102', 'HR'),
        ('103', 'บัญชี'),
        ('other', 'อื่นๆ'),
    ], string='แผนก', compute='_compute_department', store=True,
       help='แผนกที่รับสายตามรหัสจุดหมายสุดท้าย (101=เช่าขาย, 102=HR, 103=บัญชี)')
    department_name = fields.Char('ชื่อแผนก', compute='_compute_department', store=True,
                                   help='ชื่อแผนกจากจุดหมายสุดท้าย')
    
    # ทิศทางสาย
    direction = fields.Selection([
        ('inbound', 'สายเข้า'),
        ('outbound', 'สายออก'),
        ('local', 'ภายใน'),
    ], string='ทิศทางสาย', tracking=True,
       help='ทิศทางของสาย: inbound, outbound, local')
    
    # เวลารอสาย
    ring_time = fields.Integer('เวลารอสาย (วินาที)', 
                               help='ระยะเวลาที่รอสาย (เป็นวินาที)')
    
    # สถานะสาย
    call_result = fields.Selection([
        ('answered', 'รับสาย'),
        ('missed', 'ไม่รับสาย'),
        ('cancelled', 'ยกเลิก'),
        ('failed', 'ล้มเหลว'),
    ], string='ผลการโทร', tracking=True,
       help='สถานะของสาย: answered, missed, cancelled, failed')
    
    # ระยะเวลาสนทนา
    call_duration = fields.Integer('ระยะเวลาสนทนา (วินาที)',
                                   help='ระยะเวลาคุยสาย (กรณีรับสาย) หรือระยะเวลาของสาย (กรณีไม่รับสาย)')
    call_duration_display = fields.Char('ระยะเวลา', compute='_compute_duration_display')
    
    # ข้อมูลเพิ่มเติม
    data1 = fields.Char('Data1', help='Data1 จากข้อมูลที่ระบุภายในสาย (ถ้ามี)')
    data2 = fields.Char('Data2', help='Data2 จากข้อมูลที่ระบุภายในสาย (ถ้ามี)')
    ref_1 = fields.Char('Reference 1', help='ReferenceNo.1 ที่ระบุในสาย (ถ้ามี)')
    ref_2 = fields.Char('Reference 2', help='ReferenceNo.2 ที่ระบุในสาย (ถ้ามี)')
    
    # ==================== ข้อมูลเพิ่มเติม ====================
    
    # ไฟล์เสียง
    recording_url = fields.Char('URL ไฟล์เสียง')
    recording_file = fields.Binary('ไฟล์เสียง')
    recording_filename = fields.Char('ชื่อไฟล์เสียง')
    
    # ข้อมูลดิบ
    raw_data = fields.Text('ข้อมูลดิบ (JSON)')
    
    # เชื่อมโยงกับ Partner
    partner_id = fields.Many2one('res.partner', string='ลูกค้า/คู่ค้า', 
                                  compute='_compute_partner', store=True)
    
    # หมายเหตุ
    note = fields.Text('หมายเหตุ')
    
    # Flag สำหรับตรวจสอบว่ามาจาก Webhook
    is_from_webhook = fields.Boolean('จาก Webhook', default=True)
    
    # ==================== Legacy Fields (เพื่อความเข้ากันได้) ====================
    call_type = fields.Selection([
        ('inbound', 'สายเข้า'),
        ('outbound', 'สายออก'),
        ('internal', 'ภายใน'),
    ], string='ประเภทสาย', compute='_compute_call_type', store=True)
    
    caller_number = fields.Char('เบอร์โทรเข้า', compute='_compute_legacy_fields', store=True)
    called_number = fields.Char('เบอร์ที่โทรหา', compute='_compute_legacy_fields', store=True)
    extension = fields.Char('Extension', compute='_compute_legacy_fields', store=True)
    
    call_status = fields.Selection([
        ('ringing', 'กำลังดัง'),
        ('answered', 'รับสาย'),
        ('missed', 'ไม่รับสาย'),
        ('busy', 'สายไม่ว่าง'),
        ('failed', 'ไม่สำเร็จ'),
        ('voicemail', 'ฝากข้อความ'),
    ], string='สถานะสาย', compute='_compute_call_status', store=True)
    
    call_time = fields.Datetime('เวลาโทร', compute='_compute_call_time', store=True)
    answer_time = fields.Datetime('เวลารับสาย')
    end_time = fields.Datetime('เวลาวางสาย', compute='_compute_end_time', store=True)
    duration = fields.Integer('ระยะเวลา (วินาที)', compute='_compute_duration', store=True)
    duration_display = fields.Char('ระยะเวลา', compute='_compute_duration_display')

    # ==================== COMPUTE METHODS ====================

    def _convert_to_thai_timezone(self, dt):
        """แปลง UTC datetime เป็น datetime ของประเทศไทย"""
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        thai_tz = pytz.timezone('Asia/Bangkok')
        return dt.astimezone(thai_tz)

    @api.depends('start_stamp', 'end_stamp')
    def _compute_thai_datetime(self):
        """คำนวณเวลาในรูปแบบประเทศไทย และ UTC"""
        thai_tz = pytz.timezone('Asia/Bangkok')
        
        for record in self:
            # เวลาเริ่มสาย - Odoo เก็บ datetime เป็น UTC naive datetime
            if record.start_stamp:
                # UTC format (ค่าตรงจาก field ซึ่งเป็น UTC)
                record.start_stamp_utc = record.start_stamp.strftime('%d/%m/%Y %H:%M:%S')
                
                # แปลงเป็นเวลาไทย (UTC + 7)
                utc_dt = pytz.UTC.localize(record.start_stamp)
                thai_dt = utc_dt.astimezone(thai_tz)
                record.start_stamp_thai = thai_dt.strftime('%d/%m/%Y %H:%M:%S')
                record.start_date_thai = thai_dt.strftime('%d/%m/%Y')
                record.start_time_thai = thai_dt.strftime('%H:%M:%S')
            else:
                record.start_stamp_thai = ''
                record.start_date_thai = ''
                record.start_time_thai = ''
                record.start_stamp_utc = ''
            
            # เวลาจบสาย
            if record.end_stamp:
                # UTC format
                record.end_stamp_utc = record.end_stamp.strftime('%d/%m/%Y %H:%M:%S')
                
                # แปลงเป็นเวลาไทย
                utc_dt = pytz.UTC.localize(record.end_stamp)
                thai_dt = utc_dt.astimezone(thai_tz)
                record.end_stamp_thai = thai_dt.strftime('%d/%m/%Y %H:%M:%S')
            else:
                record.end_stamp_thai = ''
                record.end_stamp_utc = ''

    @api.depends('direction', 'last_destination', 'caller_id_name')
    def _compute_department(self):
        """คำนวณแผนกจากทิศทางสาย
        - สายเข้า (inbound) → เช็คจาก last_destination
        - สายออก (outbound) → เช็คจาก caller_id_name
        """
        department_mapping = {
            '101': ('101', 'เช่าขาย'),
            '102': ('102', 'HR'),
            '103': ('103', 'บัญชี'),
        }
        for record in self:
            # เลือกฟิลด์ที่จะเช็คตามทิศทางสาย
            if record.direction == 'inbound':
                # สายเข้า → เช็คจาก last_destination
                check_value = record.last_destination or ''
            elif record.direction == 'outbound':
                # สายออก → เช็คจาก caller_id_name
                check_value = record.caller_id_name or ''
            else:
                # local หรืออื่นๆ → เช็คจาก last_destination
                check_value = record.last_destination or ''
            
            # ตรวจสอบว่าค่าที่เช็คตรงกับรหัสแผนกหรือไม่
            dept_code = None
            dept_name = ''
            for code in department_mapping:
                if check_value.startswith(code) or check_value == code:
                    dept_code, dept_name = department_mapping[code]
                    break
            
            if dept_code:
                record.department_code = dept_code
                record.department_name = dept_name
            else:
                # ไม่ตรงกับรหัสแผนก → เป็นค่าว่าง
                record.department_code = False
                record.department_name = ''

    @api.depends('direction', 'caller_id_number', 'caller_destination', 'start_stamp')
    def _compute_name(self):
        for record in self:
            direction_str = dict(record._fields['direction'].selection or {}).get(record.direction, '')
            if record.direction == 'inbound':
                phone = record.caller_id_number or record.source_number
            else:
                phone = record.caller_destination or record.last_destination
            time_str = record.start_stamp.strftime('%Y-%m-%d %H:%M') if record.start_stamp else ''
            record.name = f"[{direction_str}] {phone or 'N/A'} - {time_str}"

    @api.depends('call_duration')
    def _compute_duration_display(self):
        for record in self:
            duration = record.call_duration or 0
            if duration > 0:
                minutes = duration // 60
                seconds = duration % 60
                record.call_duration_display = f"{minutes:02d}:{seconds:02d}"
                record.duration_display = record.call_duration_display
            else:
                record.call_duration_display = ''
                record.duration_display = ''

    @api.depends('caller_id_number', 'caller_destination', 'direction')
    def _compute_partner(self):
        """ค้นหา Partner จากเบอร์โทร"""
        for record in self:
            if record.direction == 'inbound':
                phone = record.caller_id_number or record.source_number
            else:
                phone = record.caller_destination or record.last_destination
            
            if phone:
                clean_phone = phone.replace('+', '').replace('-', '').replace(' ', '')
                partner = self.env['res.partner'].search([
                    '|', '|', '|',
                    ('phone', 'ilike', clean_phone[-9:]),
                    ('mobile', 'ilike', clean_phone[-9:]),
                    ('phone', 'ilike', phone),
                    ('mobile', 'ilike', phone),
                ], limit=1)
                record.partner_id = partner.id if partner else False
            else:
                record.partner_id = False

    @api.depends('direction')
    def _compute_call_type(self):
        """แปลง direction เป็น call_type"""
        for record in self:
            if record.direction == 'local':
                record.call_type = 'internal'
            else:
                record.call_type = record.direction or 'inbound'

    @api.depends('caller_id_number', 'source_number', 'caller_destination', 'last_destination', 'caller_id_name')
    def _compute_legacy_fields(self):
        """คำนวณ field เก่าจาก field ใหม่"""
        for record in self:
            record.caller_number = record.caller_id_number or record.source_number
            record.called_number = record.caller_destination or record.last_destination
            record.extension = record.caller_id_name

    @api.depends('call_result')
    def _compute_call_status(self):
        """แปลง call_result เป็น call_status"""
        for record in self:
            mapping = {
                'answered': 'answered',
                'missed': 'missed',
                'cancelled': 'missed',
                'failed': 'failed',
            }
            record.call_status = mapping.get(record.call_result, 'answered')

    @api.depends('start_stamp')
    def _compute_call_time(self):
        for record in self:
            record.call_time = record.start_stamp

    @api.depends('end_stamp')
    def _compute_end_time(self):
        for record in self:
            record.end_time = record.end_stamp

    @api.depends('call_duration')
    def _compute_duration(self):
        for record in self:
            record.duration = record.call_duration or 0

    # ==================== BLOCK CREATE/WRITE/UNLINK ====================
    
    @api.model
    def create(self, vals):
        """อนุญาตให้สร้างได้เฉพาะจาก Webhook เท่านั้น"""
        if not self.env.context.get('from_webhook'):
            raise UserError('❌ ไม่สามารถเพิ่มข้อมูลได้\n\nข้อมูลประวัติการโทรจะถูกเพิ่มโดยอัตโนมัติจาก Yalecom เท่านั้น')
        
        # ใช้ xml_cdr_uuid เป็น call_id ถ้าไม่มี call_id
        if vals.get('xml_cdr_uuid') and not vals.get('call_id'):
            vals['call_id'] = vals['xml_cdr_uuid']
        
        return super(YalecomCallLog, self).create(vals)
    
    def write(self, vals):
        """อนุญาตให้แก้ไขได้เฉพาะจาก Webhook เท่านั้น"""
        if not self.env.context.get('from_webhook'):
            allowed_fields = {'message_follower_ids', 'message_ids', 'activity_ids', 'note'}
            if not set(vals.keys()).issubset(allowed_fields):
                raise UserError('❌ ไม่สามารถแก้ไขข้อมูลได้\n\nข้อมูลประวัติการโทรไม่สามารถแก้ไขได้')
        return super(YalecomCallLog, self).write(vals)
    
    def unlink(self):
        """ไม่อนุญาตให้ลบ"""
        raise UserError('❌ ไม่สามารถลบข้อมูลได้\n\nข้อมูลประวัติการโทรไม่สามารถลบได้')


class YalecomWebhookLog(models.Model):
    """บันทึก Webhook ทั้งหมดที่ได้รับ (Read Only)"""
    _name = 'yalecom.webhook.log'
    _description = 'Yalecom Webhook Log'
    _order = 'create_date desc'

    name = fields.Char('ชื่อ', default=lambda self: f"Webhook {fields.Datetime.now()}")
    endpoint = fields.Char('Endpoint')
    method = fields.Char('Method')
    headers = fields.Text('Headers')
    body = fields.Text('Body (JSON)')
    ip_address = fields.Char('IP Address')
    status = fields.Selection([
        ('success', 'สำเร็จ'),
        ('error', 'ผิดพลาด'),
    ], string='สถานะ', default='success')
    error_message = fields.Text('ข้อความผิดพลาด')
    processed = fields.Boolean('ประมวลผลแล้ว', default=False)

    @api.model
    def create(self, vals):
        if not self.env.context.get('from_webhook'):
            raise UserError('❌ ไม่สามารถเพิ่มข้อมูลได้\n\nข้อมูล Webhook Log จะถูกเพิ่มโดยอัตโนมัติเท่านั้น')
        return super(YalecomWebhookLog, self).create(vals)
    
    def write(self, vals):
        if not self.env.context.get('from_webhook'):
            raise UserError('❌ ไม่สามารถแก้ไขข้อมูลได้\n\nข้อมูล Webhook Log ไม่สามารถแก้ไขได้')
        return super(YalecomWebhookLog, self).write(vals)
    
    def unlink(self):
        raise UserError('❌ ไม่สามารถลบข้อมูลได้\n\nข้อมูล Webhook Log ไม่สามารถลบได้')


class YalecomConfig(models.Model):
    """ตั้งค่า Yalecom API"""
    _name = 'yalecom.config'
    _description = 'Yalecom Configuration'

    name = fields.Char('ชื่อการตั้งค่า', required=True, default='Default')
    company_id_yalecom = fields.Char('Company ID (Yalecom)', 
                                      help='Company ID ที่ได้รับจาก Yalecom')
    api_key = fields.Char('API Key', help='Key ที่ได้รับจาก Yalecom')
    api_secret = fields.Char('API Secret')
    
    # Database & URL Settings
    database_name = fields.Char('ชื่อ Database', compute='_compute_database_name', store=True,
                                readonly=False, help='ชื่อ Database ของ Odoo (ดึงอัตโนมัติจากที่ login)')
    base_url = fields.Char('Base URL', 
                           help='URL หลักของ Odoo เช่น https://npderp.com')
    webhook_url = fields.Char('Webhook URL (ไม่มี db)', compute='_compute_webhook_url')
    webhook_url_full = fields.Char('Webhook URL (ส่งให้ Yalecom)', compute='_compute_webhook_url',
                                    help='URL สำหรับส่งให้ Yalecom (รวม database parameter)')
    
    is_active = fields.Boolean('เปิดใช้งาน', default=True)
    
    auto_download_recording = fields.Boolean('ดาวน์โหลดไฟล์เสียงอัตโนมัติ', default=False)
    log_all_webhooks = fields.Boolean('บันทึก Webhook ทั้งหมด (Debug)', default=True)

    @api.depends_context('uid')
    def _compute_database_name(self):
        """ดึงชื่อ database จากที่ login อยู่"""
        for record in self:
            if not record.database_name:
                record.database_name = self.env.cr.dbname

    def _compute_webhook_url(self):
        """สร้าง Webhook URL"""
        system_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        current_db = self.env.cr.dbname
        
        for record in self:
            # ใช้ base_url ที่ตั้งค่าไว้ หรือใช้ค่าจากระบบ
            base = record.base_url or system_base_url or ''
            base = base.rstrip('/')
            
            # URL ไม่มี db parameter
            record.webhook_url = f"{base}/api/yalecom/callback"
            
            # URL พร้อม db parameter (ใช้ค่าที่ตั้งไว้ หรือ db ปัจจุบัน)
            db_name = record.database_name or current_db
            if db_name:
                record.webhook_url_full = f"{base}/api/yalecom/callback?db={db_name}"
            else:
                record.webhook_url_full = record.webhook_url

    @api.model
    def create(self, vals):
        """ตั้งค่า database_name อัตโนมัติเมื่อสร้างใหม่"""
        if not vals.get('database_name'):
            vals['database_name'] = self.env.cr.dbname
        return super(YalecomConfig, self).create(vals)

    def action_test_connection(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ทดสอบการเชื่อมต่อ',
                'message': 'ยังไม่มีการตั้งค่า API สำหรับทดสอบ กรุณาติดต่อ Yalecom เพื่อขอข้อมูล API',
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_copy_webhook_url(self):
        """แสดง Webhook URL สำหรับคัดลอก"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '📋 Webhook URL สำหรับ Yalecom',
                'message': f'คัดลอก URL นี้ส่งให้ Yalecom:\n\n{self.webhook_url_full}',
                'type': 'info',
                'sticky': True,
            }
        }
