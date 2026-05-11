# -*- coding: utf-8 -*-
import base64
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EmployeeWarningController(http.Controller):

    @http.route(
        '/api/employee_warning/attachment/<int:attachment_id>',
        type='http', auth='user', methods=['GET'], csrf=False,
    )
    def download_warning_attachment(self, attachment_id, **kwargs):
        """ดาวน์โหลดไฟล์แนบใบเตือน"""
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
        if not attachment.exists():
            return request.not_found()

        # ตรวจสอบว่าเป็น attachment ของ employee.warning.line
        if attachment.res_model != 'employee.warning.line':
            return request.not_found()

        try:
            data = base64.b64decode(attachment.datas) if attachment.datas else b''
            filename = attachment.name or 'warning_attachment'
            mimetype = attachment.mimetype or 'application/octet-stream'

            headers = [
                ('Content-Type', mimetype),
                ('Content-Length', len(data)),
                ('Content-Disposition',
                 'attachment; filename="%s"' % filename),
            ]
            return request.make_response(data, headers=headers)
        except Exception as e:
            _logger.error('Error downloading attachment %s: %s', attachment_id, e)
            return request.not_found()

    @http.route(
        '/api/employee_warning/list',
        type='json', auth='user', methods=['POST'], csrf=False,
    )
    def list_warnings(self, employee_code=None, **kwargs):
        """JSON endpoint สำหรับดึงรายการใบเตือน
        POST body: {"employee_code": "E001"}
        """
        if not employee_code:
            return {'error': 'employee_code is required'}
        result = request.env['employee.warning'].sudo() \
            .api_get_warnings_by_employee_code(employee_code)
        return result

    @http.route(
        '/api/employee_warning/count',
        type='json', auth='user', methods=['POST'], csrf=False,
    )
    def count_warnings(self, employee_code=None, **kwargs):
        """JSON endpoint คืนจำนวนใบเตือน"""
        if not employee_code:
            return {'count': 0}
        count = request.env['employee.warning'].sudo() \
            .api_get_warning_count(employee_code)
        return {'count': count}
