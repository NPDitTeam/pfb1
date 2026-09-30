# -*- coding: utf-8 -*-
"""ตัวช่วย AI-IT : ใบโยกสินค้า (stock.api.transfer) ตัดสต๊อกไม่ผ่านเพราะของไม่พอ

ต่างจากเคสใบสั่งขาย/ใบจัดส่งตรงที่ "ของที่ไม่พอ" ไม่ได้อยู่ในฐานนี้ แต่อยู่ใน
ฐานต้นทางที่ผู้ใช้เลือกไว้ในช่อง "เลือกฐานข้อมูล" ของใบโยก การเติมสต๊อกจึงต้อง
ยิงข้ามฐานผ่าน /api/adjust_stock ของโมดูล stock_api_access ที่ฐานต้นทาง

ถ้าฐานต้นทางเป็นฐานเดียวกับที่รันอยู่ จะเติมในเครื่องตรง ๆ ไม่ต้องยิง HTTP

บัญชีที่ใช้ยิงข้ามฐานอ่านจาก System Parameter เท่านั้น ไม่ฝังไว้ในโค้ด
    stock_api_transfer.base_url      เช่น https://npderp.com
    stock_api_transfer.api_login
    stock_api_transfer.api_password
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

TRANSFER_MODEL = 'stock.api.transfer'

# ใบที่ยังตัดสต๊อกไม่สำเร็จ = ยังไม่ถึงขั้น confirmed
OPEN_STATES = ('draft', 'to_approve', 'approved', 'waiting', 'rejected')

BASE_URL_PARAM = 'stock_api_transfer.base_url'
LOGIN_PARAM = 'stock_api_transfer.api_login'
PASSWORD_PARAM = 'stock_api_transfer.api_password'

SETUP_HINT = ('ยังไม่ได้ตั้งค่าบัญชีสำหรับเชื่อมฐานข้ามเครื่อง '
              'ให้ฝ่าย IT ไปตั้งที่ Settings > Technical > System Parameters '
              'คีย์ %s, %s และ %s'
              % (BASE_URL_PARAM, LOGIN_PARAM, PASSWORD_PARAM))


class NpdAiItStockTransferFix(models.AbstractModel):
    _name = 'npd.ai.it.stock.transfer.fix'
    _description = 'ตัวช่วย AI-IT : เติมสต๊อกให้ใบโยกสินค้าข้ามฐาน'

    # ------------------------------------------------------------------
    # หาเอกสาร
    # ------------------------------------------------------------------
    @api.model
    def available(self):
        """โมดูลใบโยกสินค้าติดตั้งอยู่ในฐานนี้ไหม"""
        return TRANSFER_MODEL in self.env

    @api.model
    def find_transfer(self, ref):
        """หาใบโยกจากสิ่งที่พนักงานพิมพ์มา

        รับได้ทั้งเลขที่เอกสาร (TRF/2026/0224) และเลขที่ระบบ (#206 หรือ 206)
        เพราะใบที่ตัดไม่ผ่านมักยังไม่มีเลขที่ — เลขรันถูกออกตอนกดยืนยันสำเร็จ
        เท่านั้น ใบที่ค้างอยู่จึงยังชื่อ "New" ทุกใบ
        """
        if not self.available():
            return None
        ref = (ref or '').strip()
        if not ref:
            return None
        Transfer = self.env[TRANSFER_MODEL].sudo()

        rec = Transfer.search([('name', '=', ref)], limit=1)
        if rec:
            return rec

        digits = ref.lstrip('#').strip()
        if digits.isdigit():
            rec = Transfer.browse(int(digits))
            if rec.exists():
                return rec
        return None

    @api.model
    def pending_transfers(self, limit=15):
        """ใบโยกที่ยังตัดสต๊อกไม่สำเร็จ เรียงใบล่าสุดก่อน

        ใช้ตอนพนักงานหาเลขที่เอกสารไม่เจอ (ใบที่ค้างยังไม่มีเลขรัน)
        """
        if not self.available():
            return None
        return self.env[TRANSFER_MODEL].sudo().search(
            [('state', 'in', OPEN_STATES)], order='id desc', limit=limit)

    # ------------------------------------------------------------------
    # เชื่อมฐานต้นทาง
    # ------------------------------------------------------------------
    @api.model
    def _api_config(self):
        """คืน (base_url, login, password, error) — อ่านจาก System Parameter"""
        get = self.env['ir.config_parameter'].sudo().get_param
        base_url = (get(BASE_URL_PARAM) or '').strip().rstrip('/')
        login = (get(LOGIN_PARAM) or '').strip()
        secret = get(PASSWORD_PARAM) or ''
        if not base_url or not login or not secret:
            return None, None, None, SETUP_HINT
        return base_url, login, secret, None

    @api.model
    def _api_session(self, db_name):
        """ล็อกอินเข้าฐานต้นทางแล้วคืน (session, base_url, error)"""
        try:
            import requests
        except ImportError:
            return None, None, 'เครื่องนี้ยังไม่ได้ติดตั้งไลบรารี requests'

        base_url, login, secret, error = self._api_config()
        if error:
            return None, None, error
        try:
            session = requests.Session()
            session.post(
                '%s/web/session/authenticate' % base_url,
                json={'jsonrpc': '2.0', 'method': 'call',
                      'params': {'db': db_name, 'login': login,
                                 'password': secret}, 'id': 1},
                timeout=60,
            )
            if not session.cookies.get('session_id'):
                return None, None, ('เข้าระบบฐาน %s ไม่ได้ '
                                    'ให้ฝ่าย IT ตรวจบัญชีที่ตั้งไว้ใน '
                                    'System Parameter' % db_name)
            return session, base_url, None
        except Exception as err:
            _logger.exception('AI-IT โยกสินค้า: ต่อฐาน %s ไม่ได้', db_name)
            return None, None, 'ต่อฐาน %s ไม่ได้: %s' % (db_name, err)

    @api.model
    def _remote_qty_map(self, db_name):
        """{(รหัสสินค้า, id คลัง): จำนวนคงเหลือ} ของฐานต้นทาง

        คืน (mapping, error) — ถ้าอ่านไม่ได้ mapping จะเป็น None
        """
        session, base_url, error = self._api_session(db_name)
        if error:
            return None, error
        try:
            response = session.post(
                '%s/api/get_stock' % base_url,
                json={'db': db_name}, timeout=120,
                headers={'Content-Type': 'application/json'},
            )
            payload = (response.json() or {}).get('result') or {}
            rows = payload.get('result') or []
        except Exception as err:
            _logger.exception('AI-IT โยกสินค้า: อ่านสต๊อกฐาน %s ไม่ได้', db_name)
            return None, 'อ่านสต๊อกจากฐาน %s ไม่ได้: %s' % (db_name, err)

        mapping = {}
        for row in rows:
            key = ((row.get('default_code') or '').strip(),
                   int(row.get('location_id') or 0))
            mapping[key] = mapping.get(key, 0.0) + float(row.get('quantity') or 0.0)
        return mapping, None

    @api.model
    def _local_qty(self, default_code, location_id):
        product = self.env['product.product'].sudo().search(
            [('default_code', '=', default_code)], limit=1)
        if not product:
            return 0.0
        quants = self.env['stock.quant'].sudo().search([
            ('product_id', '=', product.id),
            ('location_id', '=', location_id),
        ])
        return sum(quants.mapped('quantity'))

    # ------------------------------------------------------------------
    # วิเคราะห์
    # ------------------------------------------------------------------
    @api.model
    def analyze(self, transfer):
        """เทียบ "จำนวนขอตัด" กับของจริงในคลังต้นทาง

        คืน (all_items, shortage_items, error) — item เก็บลง session เป็น JSON ได้
        """
        transfer = transfer.sudo()
        db_name = transfer.database_selection
        if not db_name:
            return [], [], 'ใบนี้ยังไม่ได้เลือกฐานข้อมูลต้นทาง'

        is_local = (db_name == self.env.cr.dbname)
        qty_map = None
        if not is_local:
            qty_map, error = self._remote_qty_map(db_name)
            if error:
                return [], [], error

        all_items = []
        for line in transfer.line_ids:
            code = (line.default_code or '').strip()
            location_id = int(line.location_id or 0)
            need = float(line.request_qty or 0.0)
            if not code or not location_id or need <= 0:
                continue
            if is_local:
                current = self._local_qty(code, location_id)
            else:
                current = float(qty_map.get((code, location_id), 0.0))
            all_items.append({
                'line_id': line.id,
                'code': code,
                'name': line.product_name or code,
                'location_id': location_id,
                'location_name': (line.location_api_id.name
                                  if line.location_api_id else '') or '',
                'need': need,
                'current': current,
                'missing': max(need - current, 0.0),
                'target': None,
            })

        all_items.sort(key=lambda i: i['name'])
        shortage = [i for i in all_items if i['missing'] > 0]
        return all_items, shortage, None

    # ------------------------------------------------------------------
    # เติมสต๊อก
    # ------------------------------------------------------------------
    @api.model
    def apply_topup(self, transfer, items):
        """เติมสต๊อกที่คลังต้นทางให้ถึงจำนวนที่พนักงานนับได้จริง

        คืน (applied, error) — applied เป็น list ของ
        {code, name, location_id, before, added, after}

        เติมอย่างเดียว ไม่มีเส้นทางลดสต๊อก ทั้งฝั่งในเครื่องและฝั่ง API
        """
        transfer = transfer.sudo()
        db_name = transfer.database_selection
        payload = []
        by_code = {}
        for item in items:
            target = float(item.get('target') or 0.0)
            if target <= 0:
                continue
            payload.append({
                'default_code': item['code'],
                'location_id': item['location_id'],
                'target_qty': target,
            })
            by_code[(item['code'], item['location_id'])] = item

        if not payload:
            return [], None

        if db_name == self.env.cr.dbname:
            result, error = self._apply_local(payload)
        else:
            result, error = self._apply_remote(db_name, payload)
        if error:
            return [], error

        applied = []
        for row in result:
            key = ((row.get('default_code') or '').strip(),
                   int(row.get('location_id') or 0))
            item = by_code.get(key) or {}
            applied.append({
                'code': key[0],
                'name': item.get('name') or key[0],
                'location_id': key[1],
                'location_name': item.get('location_name') or '',
                'before': float(row.get('before') or 0.0),
                'added': float(row.get('added') or 0.0),
                'after': float(row.get('after') or 0.0),
            })
        return applied, None

    @api.model
    def _apply_local(self, payload):
        """ฐานต้นทางคือฐานเดียวกับที่รันอยู่ — ปรับสต๊อกตรง ๆ"""
        Product = self.env['product.product'].sudo()
        Location = self.env['stock.location'].sudo()
        Quant = self.env['stock.quant'].sudo()
        result = []
        for row in payload:
            code = row['default_code']
            location_id = row['location_id']
            target = float(row['target_qty'])
            product = Product.search([('default_code', '=', code)], limit=1)
            if not product:
                return None, 'ไม่พบสินค้ารหัส %s ในฐานนี้' % code
            location = Location.browse(location_id)
            if not location.exists() or location.usage != 'internal':
                return None, 'คลัง id=%s ใช้เติมสต๊อกไม่ได้' % location_id

            before = self._local_qty(code, location_id)
            if target <= before:
                result.append({'default_code': code, 'location_id': location_id,
                               'before': before, 'added': 0.0, 'after': before})
                continue
            quant = Quant.search([
                ('product_id', '=', product.id),
                ('location_id', '=', location_id),
                ('lot_id', '=', False),
                ('package_id', '=', False),
                ('owner_id', '=', False),
            ], limit=1)
            if quant:
                quant.with_context(inventory_mode=True).write({
                    'inventory_quantity': quant.quantity + (target - before),
                })
            else:
                Quant.with_context(inventory_mode=True).create({
                    'product_id': product.id,
                    'location_id': location_id,
                    'inventory_quantity': target - before,
                })
            after = self._local_qty(code, location_id)
            result.append({'default_code': code, 'location_id': location_id,
                           'before': before, 'added': after - before,
                           'after': after})
        return result, None

    @api.model
    def _apply_remote(self, db_name, payload):
        """ยิงไปเติมที่ฐานต้นทางผ่าน /api/adjust_stock"""
        session, base_url, error = self._api_session(db_name)
        if error:
            return None, error
        try:
            response = session.post(
                '%s/api/adjust_stock' % base_url,
                json={'db': db_name, 'items': payload}, timeout=120,
                headers={'Content-Type': 'application/json'},
            )
            body = response.json() or {}
        except Exception as err:
            _logger.exception('AI-IT โยกสินค้า: เติมสต๊อกฐาน %s ไม่สำเร็จ', db_name)
            return None, 'เติมสต๊อกที่ฐาน %s ไม่สำเร็จ: %s' % (db_name, err)

        payload_result = body.get('result') or {}
        if payload_result.get('status') != 200:
            reason = (payload_result.get('error')
                      or body.get('error')
                      or 'ฐานต้นทางตอบกลับผิดปกติ')
            if isinstance(reason, dict):
                reason = reason.get('data', {}).get('message') or str(reason)
            return None, 'ฐาน %s เติมสต๊อกให้ไม่สำเร็จ: %s' % (db_name, reason)
        return payload_result.get('result') or [], None
