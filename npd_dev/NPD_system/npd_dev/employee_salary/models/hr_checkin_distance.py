# -*- coding: utf-8 -*-
import requests
from odoo import models, fields, api
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

API_URL = "https://npdhrms.com/api_checkin_distance.php"

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
    ("ทดสอบ", "ทดสอบ"),
    ("ทดสอบ1", "ทดสอบ1"),
]


class HrCheckinDistance(models.Model):
    _name = 'hr.checkin.distance'
    _description = 'Check-in Distance Setting'
    _rec_name = 'branch_id'

    # field สาขาเดิม (เก็บไว้สำหรับอัพเดท)
    branch_name = fields.Selection(selection=BRANCH_SELECTION, string="🏢 สาขา (เดิม)")
    
    # field สาขาใหม่ Many2one
    branch_id = fields.Many2one('hr.branch.custom', string="🏢 สาขา")

    distance_meter = fields.Char("📐 ระยะห่างที่อนุญาต (เมตร)", required=True, default=50)
    latitude = fields.Char("📍 ละติจูด")
    longitude = fields.Char("📍 ลองจิจูด")

    # 🗺️ HTML field สำหรับแสดงแผนที่แบบ static
    map_display = fields.Html(string="แผนที่", compute='_compute_map_display', store=False)

    # 🗺️ NEW: Field สำหรับ interactive map widget
    interactive_map_dummy = fields.Char(string="Interactive Map", store=False, default="dummy")

    # 💡 NEW: Field ชั่วคราวสำหรับเก็บ ID ของ PHP API ระหว่างการซิงค์
    php_id = fields.Integer(store=False)

    _sql_constraints = [
        ('branch_id_unique', 'unique(branch_id)', 'สาขานี้ถูกตั้งค่าไว้แล้ว ห้ามซ้ำ!')
    ]

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

    @api.depends('branch_id', 'latitude', 'longitude', 'distance_meter')
    def _compute_map_display(self):
        for record in self:
            lat = float(record.latitude or '13.7563')
            lng = float(record.longitude or '100.5018')
            distance = int(record.distance_meter or '100')
            branch = record.branch_id.name if record.branch_id else 'ไม่ระบุสาขา'

            # สร้าง Google Maps Static API URL
            static_map_url = f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lng}&zoom=16&size=600x400&markers=color:red%7C{lat},{lng}&key=AIzaSyCHKkMOyDdI29v52SULcRx_OcB3i-MD7lw"

            # สร้าง URL สำหรับเปิด Google Maps
            google_maps_url = f"https://www.google.com/maps?q={lat},{lng}&z=16"
            navigation_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"

            # สร้าง HTML สำหรับแสดงแผนที่
            map_html = f'''
            <div style="border: 2px solid #007bff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.1); background: white;">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #007bff 0%, #0056b3 100%); color: white; padding: 20px; text-align: center;">
                    <h3 style="margin: 0; display: flex; align-items: center; justify-content: center;">
                        <i class="fa fa-map-marker-alt" style="margin-right: 12px; font-size: 24px; color: #ffeb3b;"></i>
                        {branch}
                    </h3>
                </div>

                <!-- Info Panel -->
                <div style="background: #f8f9fa; padding: 20px; border-bottom: 2px solid #dee2e6;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; text-align: center;">
                        <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                            <div style="color: #dc3545; font-size: 18px; margin-bottom: 5px;">
                                <i class="fa fa-map-pin"></i>
                            </div>
                            <strong style="color: #495057; font-size: 14px;">ละติจูด</strong><br>
                            <span style="color: #007bff; font-weight: bold;">{lat:.6f}</span>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                            <div style="color: #dc3545; font-size: 18px; margin-bottom: 5px;">
                                <i class="fa fa-map-pin"></i>
                            </div>
                            <strong style="color: #495057; font-size: 14px;">ลองจิจูด</strong><br>
                            <span style="color: #007bff; font-weight: bold;">{lng:.6f}</span>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                            <div style="color: #28a745; font-size: 18px; margin-bottom: 5px;">
                                <i class="fa fa-crosshairs"></i>
                            </div>
                            <strong style="color: #495057; font-size: 14px;">ระยะ Check-in</strong><br>
                            <span style="color: #28a745; font-weight: bold;">{distance} เมตร</span>
                        </div>
                    </div>
                </div>

                <!-- Static Map Preview -->
                <div style="text-align: center; padding: 0 20px 20px;">
                    <img src="{static_map_url}"
                         alt="แผนที่สาขา {branch}"
                         style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"
                         onerror="this.style.display='none';">
                </div>
    
            </div>
            '''

            record.map_display = map_html

    # ------------------------
    # 🔄 Sync Odoo → PHP
    # ------------------------
    def _sync_to_api(self, action):
        for rec in self:
            try:
                # ส่งชื่อสาขาจาก branch_id
                branch_name = rec.branch_id.name if rec.branch_id else rec.branch_name
                
                payload = {
                    'action': action,
                    'branch_name': branch_name or '',
                    'distance_meter': rec.distance_meter or 0,
                    'latitude': rec.latitude or 0.0,
                    'longitude': rec.longitude or 0.0,
                }

                response = requests.post(API_URL, json=payload, timeout=10)
                response.raise_for_status()
                api_response = response.json()

                if api_response.get('status') != 'success':
                    error_message = api_response.get('message', 'ไม่ทราบสาเหตุ')

                    # ถ้า create ล้มเหลวเพราะซ้ำ → retry เป็น update
                    if action == 'create' and "Branch already exists" in error_message:
                        _logger.warning("Branch '%s' already exists. Retrying as update.", branch_name)

                        payload['action'] = 'update'
                        response = requests.post(API_URL, json=payload, timeout=10)
                        response.raise_for_status()
                        api_response = response.json()

                        if api_response.get('status') != 'success':
                            raise UserError(
                                f"การซิงค์ข้อมูลล้มเหลว (Update Failed): {api_response.get('message', 'ไม่ทราบสาเหตุ')}")
                        _logger.info("Successfully synced branch '%s' as 'update'.", branch_name)
                        return

                    raise UserError(f"การซิงค์ข้อมูลล้มเหลว: {error_message}")

                _logger.info("Synced branch '%s' action=%s", branch_name, action)

            except Exception as e:
                _logger.error("API sync error: %s", e)
                raise UserError(f"ไม่สามารถซิงค์กับ API ได้: {e}")

    # ------------------------
    # 🔄 Sync PHP → Odoo
    # ------------------------
    @api.model
    def sync_all_from_api(self):
        try:
            response = requests.get(API_URL, timeout=10)
            response.raise_for_status()
            api_response = response.json()

            if api_response.get('status') == 'success' and 'data' in api_response:
                php_records = api_response['data']
                for rec in php_records:
                    branch_name = rec.get('branch_name')
                    branch_id = self._get_branch_by_name(branch_name)
                    
                    # ค้นหา record ที่มีอยู่แล้วใน Odoo โดยใช้ branch_id
                    existing_record = self.env['hr.checkin.distance'].search([('branch_id', '=', branch_id)], limit=1)

                    vals = {
                        'branch_name': branch_name,  # เก็บค่าเดิมไว้
                        'branch_id': branch_id,       # ใช้ค่าใหม่
                        'distance_meter': rec.get('distance_meter', 0),
                        'latitude': rec.get('latitude', 0),
                        'longitude': rec.get('longitude', 0),
                        'php_id': rec.get('id'),
                    }
                    if existing_record:
                        existing_record.write(vals)
                    else:
                        self.create(vals)
            else:
                raise UserError(api_response.get('message', 'การดึงข้อมูลล้มเหลว'))

        except Exception as e:
            _logger.error("Sync from API failed: %s", e)
            raise UserError(f"ไม่สามารถดึงข้อมูลจาก API ได้: {e}")

    def action_open_map_circle(self):
        """เปิดแผนที่พร้อมวงกลมรัศมี Check-in ในแท็บใหม่"""
        self.ensure_one()
        # ใช้ URL เต็ม (absolute) — ถ้าเป็น relative ฝั่ง JS จะเติม /th/ ให้ตาม
        # context ภาษา → กลายเป็น /th/web/checkin_map/<id> → website ดัก 404
        # absolute URL + namespace /web/ → browser เปิดตรง ๆ, website ไม่ lang-redirect
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        return {
            'type': 'ir.actions.act_url',
            'url': f'{base_url}/web/checkin_map/{self.id}',
            'target': 'new',
        }

    def sync_and_open_view(self):
        self.sync_all_from_api()
        return self.env.ref('employee_salary.action_hr_checkin_distance').read()[0]

    # ------------------------
    # 🔄 Override CRUD
    # ------------------------
    @api.model
    def create(self, vals):
        rec = super().create(vals)
        if not vals.get('php_id'):
            rec._sync_to_api('create')
        return rec

    def write(self, vals):
        res = super().write(vals)
        self._sync_to_api('update')
        return res

    def unlink(self):
        for rec in self:
            rec._sync_to_api('delete')
        return super().unlink()
