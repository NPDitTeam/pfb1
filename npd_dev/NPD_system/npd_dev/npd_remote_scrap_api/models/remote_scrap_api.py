# -*- coding: utf-8 -*-
import logging

from odoo import models, api

_logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None
    _logger.warning("[NPD Remote API] python 'requests' ไม่ได้ติดตั้ง — API จะคืนค่าว่าง")


class NpdRemoteScrapApi(models.AbstractModel):
    """
    Service ดึงข้อมูลสินค้าชำรุดจาก Odoo server อื่นผ่าน JSON-RPC
    เรียกใช้: self.env['npd.remote.scrap.api'].get_damaged_dict(db, login, password)
    return: dict { (location_name, bk_reference_code): total scrap_qty }
    """
    _name = 'npd.remote.scrap.api'
    _description = 'NPD Remote Scrap API (JSON-RPC)'

    BASE_URL = 'https://npderp.com'
    REASON_NAME = 'สินค้าชำรุด'
    AUTH_TIMEOUT = 30
    CALL_TIMEOUT = 60

    @api.model
    def authenticate(self, db, login, password):
        """
        Authenticate กับ Odoo server ปลายทาง
        return: requests.cookies จาก response (None ถ้าล้มเหลว)
        """
        if requests is None:
            _logger.error("[NPD Remote API] requests not installed — skip auth")
            return None
        url = f"{self.BASE_URL}/web/session/authenticate"
        payload = {
            "jsonrpc": "2.0",
            "params": {
                "db": db,
                "login": login,
                "password": password,
            },
        }
        try:
            r = requests.post(url, json=payload, timeout=self.AUTH_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            uid = (data.get('result') or {}).get('uid')
            if not uid:
                _logger.error("[NPD Remote API] auth failed for db=%s: %s", db, data)
                return None
            _logger.info("[NPD Remote API] auth success db=%s uid=%s", db, uid)
            return r.cookies
        except Exception as e:
            _logger.error("[NPD Remote API] auth exception db=%s: %s", db, e)
            return None

    @api.model
    def call_kw(self, cookies, model, method, args, kwargs=None):
        """เรียก method ของ model ปลายทางผ่าน /web/dataset/call_kw"""
        if requests is None:
            return None
        url = f"{self.BASE_URL}/web/dataset/call_kw"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": method,
                "args": args,
                "kwargs": kwargs or {},
            },
        }
        try:
            r = requests.post(url, json=payload, cookies=cookies, timeout=self.CALL_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if data.get('error'):
                _logger.error("[NPD Remote API] call_kw error model=%s method=%s: %s",
                              model, method, data['error'])
                return None
            return data.get('result')
        except Exception as e:
            _logger.error("[NPD Remote API] call_kw exception model=%s method=%s: %s",
                          model, method, e)
            return None

    @api.model
    def get_damaged_dict(self, db, login, password):
        """
        ดึง stock.scrap จาก server ปลายทางที่
            reason_code_id.name = 'สินค้าชำรุด'
            state = 'done'
        แล้วรวม scrap_qty ตาม (stock.location.name, product.product.bk_reference_code)
        """
        damaged_dict = {}

        cookies = self.authenticate(db, login, password)
        if not cookies:
            return damaged_dict

        # 1) search_read stock.scrap
        scraps = self.call_kw(
            cookies,
            'stock.scrap',
            'search_read',
            [
                [
                    ('reason_code_id.name', '=', self.REASON_NAME),
                    ('state', '=', 'done'),
                ],
                ['product_id', 'location_id', 'scrap_qty'],
            ],
        ) or []
        if not scraps:
            _logger.info("[NPD Remote API] db=%s ไม่พบ scrap ที่ตรงเงื่อนไข", db)
            return damaged_dict

        product_ids = list({s['product_id'][0] for s in scraps if s.get('product_id')})
        location_ids = list({s['location_id'][0] for s in scraps if s.get('location_id')})

        # 2) read product.product → bk_reference_code
        product_map = {}
        if product_ids:
            products = self.call_kw(
                cookies, 'product.product', 'read',
                [product_ids, ['bk_reference_code']],
            ) or []
            product_map = {p['id']: p.get('bk_reference_code') for p in products}

        # 3) read stock.location → name
        location_map = {}
        if location_ids:
            locations = self.call_kw(
                cookies, 'stock.location', 'read',
                [location_ids, ['name']],
            ) or []
            location_map = {l['id']: l.get('name') for l in locations}

        # 4) aggregate
        for s in scraps:
            if not s.get('product_id') or not s.get('location_id'):
                continue
            bk_ref = product_map.get(s['product_id'][0])
            loc_name = location_map.get(s['location_id'][0])
            if bk_ref and loc_name:
                key = (loc_name, bk_ref)
                damaged_dict[key] = damaged_dict.get(key, 0) + (s.get('scrap_qty') or 0)

        _logger.info("[NPD Remote API] db=%s รวม %s key", db, len(damaged_dict))
        return damaged_dict
