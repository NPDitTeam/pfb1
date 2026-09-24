# -*- coding: utf-8 -*-
"""API บอกสถานะพักงาน — ให้แอป HR ถามก่อนเข้าหน้าลงเวลา

คืนเฉพาะว่าถูกพักงานอยู่ไหม ช่วงไหน และเหตุผล ซึ่งเป็นเรื่องที่พนักงานคนนั้น
รู้อยู่แล้ว จึงเปิดเป็น auth='none' แบบเดียวกับ /api/employee_info ที่แอปใช้อยู่
ไม่มีข้อมูลเงินเดือนหรือข้อมูลส่วนตัวอื่นหลุดออกไป

แอปเรียกตอนกดเข้าเมนูลงเวลา ถ้าถูกพักงานให้แสดงข้อความแล้วไม่ให้กดลงเวลา
ส่วนการบันทึกเข้า-ออกจริงยังยิงไป PHP เหมือนเดิม ไม่ได้เปลี่ยน
"""
import json
import logging

from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

THAI_MONTHS_ABBR = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                    'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']


def _thai_date(value):
    """31/12/2026 -> '31 ธ.ค. 2569' (พ.ศ.) ให้แอปเอาไปแสดงได้เลย"""
    if not value:
        return ''
    return '%d %s %d' % (value.day, THAI_MONTHS_ABBR[value.month - 1],
                         value.year + 543)


def _json(payload, status=200):
    return Response(json.dumps(payload, ensure_ascii=False, default=str),
                    content_type='application/json; charset=utf-8',
                    status=status)


class SuspensionApiController(http.Controller):

    @http.route('/api/employee_suspension', type='http', auth='none',
                methods=['GET'], csrf=False, cors='*')
    def employee_suspension(self, **kwargs):
        """สถานะพักงานของพนักงาน ณ วันที่ที่ถาม (ไม่ระบุ = วันนี้)

        URL: /api/employee_suspension?employee_code=0981
             /api/employee_suspension?employee_code=0981&date=2026-09-22
        """
        employee_code = (kwargs.get('employee_code') or '').strip()
        if not employee_code:
            return _json({'status': 'error',
                          'message': 'กรุณาระบุ employee_code'}, 400)

        try:
            env = request.env(su=True)
            employee = env['employee.salary'].search(
                [('employee_code', '=', employee_code)], limit=1)
            if not employee:
                return _json({'status': 'error',
                              'message': 'ไม่พบพนักงานรหัส %s' % employee_code}, 404)

            day = fields.Date.context_today(employee)
            raw_date = (kwargs.get('date') or '').strip()
            if raw_date:
                try:
                    day = fields.Date.to_date(raw_date)
                except (ValueError, TypeError):
                    return _json({'status': 'error',
                                  'message': 'รูปแบบวันที่ไม่ถูกต้อง ใช้ YYYY-MM-DD'}, 400)

            order = env['employee.suspension'].suspension_on(employee, day)
            if not order:
                return _json({
                    'status': 'success',
                    'employee_code': employee_code,
                    'date': str(day),
                    'is_suspended': False,
                })

            return _json({
                'status': 'success',
                'employee_code': employee_code,
                'date': str(day),
                'is_suspended': True,
                'date_start': str(order.date_start),
                'date_end': str(order.date_end),
                'date_start_display': _thai_date(order.date_start),
                'date_end_display': _thai_date(order.date_end),
                'day_count': order.day_count,
                'days_remaining': max((order.date_end - day).days + 1, 0),
                'reason': order.reason or '',
                'note': order.note or '',
                'deduct_percent': order.deduct_percent,
                'message': 'คุณอยู่ในช่วงถูกพักงาน ตั้งแต่ %s ถึง %s '
                           'จึงยังลงเวลาไม่ได้' % (
                               _thai_date(order.date_start),
                               _thai_date(order.date_end)),
            })
        except Exception as error:
            _logger.exception('[SUSPENSION-API] รหัส %s ล้มเหลว: %s',
                              employee_code, error)
            return _json({'status': 'error',
                          'message': 'ระบบขัดข้อง กรุณาลองใหม่'}, 500)
