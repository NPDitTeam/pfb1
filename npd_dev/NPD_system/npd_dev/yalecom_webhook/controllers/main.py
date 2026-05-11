# -*- coding: utf-8 -*-

from odoo import http, SUPERUSER_ID, api, registry
from odoo.http import request
import json
import logging
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)

_logger.info("=" * 60)
_logger.info("🚀 YALECOM WEBHOOK CONTROLLER LOADED!")
_logger.info("=" * 60)


class YalecomWebhookController(http.Controller):
    """
    Controller สำหรับรับ Webhook/Callback จาก Yalecom
    URL: /api/yalecom/callback?db=YOUR_DATABASE
    """

    # ==================== JSON Route (Content-Type: application/json) ====================
    
    @http.route('/api/yalecom/callback', type='json', auth='none', 
                methods=['POST'], csrf=False, save_session=False)
    def yalecom_callback_json(self, **kwargs):
        """รับ Callback แบบ JSON (Content-Type: application/json)"""
        try:
            ip_address = request.httprequest.remote_addr
            
            _logger.info("=" * 60)
            _logger.info(f"📥 [JSON] Yalecom Callback from {ip_address}")
            
            # ดึงชื่อ database
            db_name = request.httprequest.args.get('db')
            if not db_name:
                return {'success': False, 'error': 'No database specified. Use ?db=your_database'}
            
            _logger.info(f"📝 Database: {db_name}")
            
            # ดึงข้อมูล JSON (Odoo parse ให้แล้ว)
            data = request.jsonrequest
            _logger.info(f"📄 Data: {json.dumps(data, ensure_ascii=False)}")
            
            # ประมวลผล
            result = self._process_with_registry(db_name, data)
            
            return {
                'success': True,
                'message': 'Callback received successfully',
                'data': result
            }
            
        except Exception as e:
            _logger.error(f"❌ Error: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    # ==================== HTTP Route (GET test) ====================
    
    @http.route('/api/yalecom/callback', type='http', auth='none', 
                methods=['GET'], csrf=False, save_session=False)
    def yalecom_callback_get(self, **kwargs):
        """ทดสอบ Endpoint (GET)"""
        _logger.info("📥 [GET] Test endpoint called")
        return request.make_response(
            json.dumps({
                'status': 'ok',
                'message': 'Yalecom Webhook Endpoint is ready',
                'timestamp': datetime.now().isoformat(),
                'usage': 'POST /api/yalecom/callback?db=YOUR_DATABASE with JSON body'
            }, ensure_ascii=False),
            headers=[('Content-Type', 'application/json; charset=utf-8')]
        )

    # ==================== Processing ====================

    def _process_with_registry(self, db_name, raw_data):
        """ประมวลผลโดยใช้ registry"""
        db_registry = registry(db_name)
        
        with db_registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {'from_webhook': True})
            result = self._process_callback(env, raw_data)
            cr.commit()
            return result

    def _process_callback(self, env, raw_data):
        """ประมวลผลข้อมูล Callback"""
        _logger.info("🔄 Processing callback...")
        
        # ดึงข้อมูลจาก 'data' field
        call_data = raw_data.get('data', {})
        
        # ถ้า data เป็น String ให้ parse
        if isinstance(call_data, str):
            try:
                call_data = json.loads(call_data)
            except:
                call_data = {}
        
        if not call_data:
            call_data = raw_data
        
        _logger.info(f"📄 Call Data: {json.dumps(call_data, ensure_ascii=False)}")
        
        # เตรียมข้อมูล
        vals = {
            'xml_cdr_uuid': call_data.get('xml_cdr_uuid'),
            'call_id': call_data.get('xml_cdr_uuid'),
            'caller_id_name': call_data.get('caller_id_name'),
            'caller_id_number': call_data.get('caller_id_number'),
            'source_number': call_data.get('source_number'),
            'caller_destination': call_data.get('caller_destination'),
            'last_destination': call_data.get('last_destination'),
            'sip_hangup_disposition': call_data.get('sip_hangup_disposition'),
            'start_stamp': self._parse_datetime(call_data.get('start_stamp')),
            'end_stamp': self._parse_datetime(call_data.get('end_stamp')),
            'direction': self._map_direction(call_data.get('direction')),
            'ring_time': int(call_data.get('ring_time') or 0),
            'call_result': self._map_call_result(call_data.get('call_result')),
            'call_duration': int(call_data.get('call_duration') or 0),
            'data1': call_data.get('data1'),
            'data2': call_data.get('data2'),
            'ref_1': call_data.get('ref_1'),
            'ref_2': call_data.get('ref_2'),
            'raw_data': json.dumps(raw_data, ensure_ascii=False),
        }
        
        if not vals['xml_cdr_uuid']:
            raise ValueError("Missing xml_cdr_uuid")
        
        # บันทึกลง database
        CallLog = env['yalecom.call.log']
        existing = CallLog.search([('xml_cdr_uuid', '=', vals['xml_cdr_uuid'])], limit=1)
        
        if existing:
            existing.write(vals)
            _logger.info(f"📝 Updated: {existing.id}")
            return {'call_log_id': existing.id, 'action': 'updated'}
        else:
            call_log = CallLog.create(vals)
            _logger.info(f"✅ Created: {call_log.id}")
            return {'call_log_id': call_log.id, 'action': 'created'}

    def _map_direction(self, direction):
        if not direction:
            return 'inbound'
        mapping = {
            'inbound': 'inbound', 'incoming': 'inbound', 'in': 'inbound',
            'outbound': 'outbound', 'outgoing': 'outbound', 'out': 'outbound',
            'local': 'local', 'internal': 'local',
        }
        return mapping.get(str(direction).lower(), 'inbound')

    def _map_call_result(self, call_result):
        if not call_result:
            return 'answered'
        mapping = {
            'answered': 'answered', 'answer': 'answered', 'connected': 'answered',
            'missed': 'missed', 'no_answer': 'missed', 'noanswer': 'missed',
            'cancelled': 'cancelled', 'cancel': 'cancelled',
            'failed': 'failed', 'fail': 'failed', 'busy': 'failed',
        }
        return mapping.get(str(call_result).lower(), 'answered')

    def _parse_datetime(self, dt_string):
        """แปลง datetime string จาก Yalecom (เวลาไทย) เป็น UTC สำหรับเก็บใน Odoo"""
        if not dt_string:
            return None
        if isinstance(dt_string, datetime):
            return dt_string
        
        thai_tz = pytz.timezone('Asia/Bangkok')
        
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']:
            try:
                # Parse เป็น naive datetime
                naive_dt = datetime.strptime(str(dt_string), fmt)
                
                # ถือว่า Yalecom ส่งมาเป็นเวลาไทย แล้วแปลงเป็น UTC
                thai_dt = thai_tz.localize(naive_dt)
                utc_dt = thai_dt.astimezone(pytz.UTC)
                
                # Return เป็น naive datetime ใน UTC (Odoo ต้องการแบบนี้)
                return utc_dt.replace(tzinfo=None)
            except:
                continue
        return None
