# -*- coding: utf-8 -*-
import json
import logging
from datetime import date

from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def _json_response(payload, status=200):
    """Helper สำหรับส่ง JSON response"""
    return Response(
        json.dumps(payload, ensure_ascii=False, default=str),
        status=status,
        content_type='application/json; charset=utf-8',
        headers=[
            ('Cache-Control', 'no-store, no-cache, must-revalidate'),
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
        ],
    )


class HolidayApiController(http.Controller):
    """REST API Controller สำหรับดึงข้อมูลวันหยุดบริษัท"""

    @http.route('/api/holidays', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def get_holidays(self, year=None, **kwargs):
        """
        GET /api/holidays?year=2026
        คืนค่ารายการวันหยุดของปีที่ระบุ (ถ้าไม่ระบุ = ปีปัจจุบัน)
        """
        # Handle CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return _json_response({}, 200)

        try:
            target_year = int(year) if year else date.today().year

            # sudo() เพราะ auth='none' ไม่มี user context
            holidays = request.env['payroll.holiday'].sudo().get_company_holidays(year=target_year)

            return _json_response({
                'status': 'success',
                'year': target_year,
                'count': len(holidays),
                'data': holidays,
            })
        except Exception as e:
            _logger.exception("Error in /api/holidays: %s", e)
            return _json_response({
                'status': 'error',
                'message': str(e),
            }, 500)

    @http.route('/api/holidays/long', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def get_long_holidays(self, year=None, min_days=2, **kwargs):
        """
        GET /api/holidays/long?year=2026&min_days=2
        คืนเฉพาะช่วงวันหยุดที่ติดกัน >= min_days วัน (default 2)
        """
        if request.httprequest.method == 'OPTIONS':
            return _json_response({}, 200)

        try:
            target_year = int(year) if year else date.today().year
            min_d = int(min_days) if min_days else 2

            ranges = request.env['payroll.holiday'].sudo().get_long_holiday_ranges(
                year=target_year, min_days=min_d
            )

            return _json_response({
                'status': 'success',
                'year': target_year,
                'min_days': min_d,
                'count': len(ranges),
                'data': ranges,
            })
        except Exception as e:
            _logger.exception("Error in /api/holidays/long: %s", e)
            return _json_response({
                'status': 'error',
                'message': str(e),
            }, 500)
