# -*- coding: utf-8 -*-
from odoo import models, api


class EmployeeWarningApi(models.Model):
    _inherit = 'employee.warning'

    @api.model
    def api_get_warnings_by_employee_code(self, employee_code):
        """
        ดึงข้อมูลใบเตือนของพนักงานจาก employee_code
        คืนค่าเป็น dict ที่ Flutter app ใช้ได้ง่าย

        Args:
            employee_code: รหัสพนักงาน (string)

        Returns:
            {
                'has_warning': bool,
                'warning_count': int,  # จำนวนรายการใบเตือน
                'employee': {
                    'code': str,
                    'firstname': str,
                    'lastname': str,
                    'position': str,
                    'branch': str,
                    'department': str,
                },
                'lines': [
                    {
                        'id': int,
                        'warning_date': 'YYYY-MM-DD',
                        'subject': str,
                        'warning_type': 'verbal' | 'written',
                        'warning_type_display': str,
                        'warning_number': int,
                        'warning_number_display': 'ครั้งที่ N',
                        'description': str,
                        'has_attachment': bool,
                        'attachment_id': int,
                        'attachment_filename': str,
                        'attachment_url': str,  # URL ดาวน์โหลดไฟล์
                    },
                    ...
                ],
            }
        """
        if not employee_code:
            return {'has_warning': False, 'warning_count': 0,
                    'employee': {}, 'lines': []}

        warning = self.search([
            ('employee_code', '=', employee_code),
        ], limit=1)

        if not warning:
            return {'has_warning': False, 'warning_count': 0,
                    'employee': {}, 'lines': []}

        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', ''
        )

        warning_type_map = {
            'verbal': 'ตักเตือนด้วยวาจา',
            'written': 'ตักเตือนเป็นหนังสือ',
        }

        lines = []
        for line in warning.warning_line_ids:
            # ค้นหา ir.attachment ที่ผูกกับ field 'attachment' ของ line นี้
            att = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'employee.warning.line'),
                ('res_id', '=', line.id),
                ('res_field', '=', 'attachment'),
            ], limit=1)

            lines.append({
                'id': line.id,
                'warning_date': line.warning_date.isoformat() if line.warning_date else '',
                'subject': line.subject or '',
                'warning_type': line.warning_type or '',
                'warning_type_display': warning_type_map.get(line.warning_type, ''),
                'warning_number': line.warning_number or 0,
                'warning_number_display': line.warning_number_display or '',
                'description': line.description or '',
                'has_attachment': bool(att),
                'attachment_id': att.id if att else 0,
                'attachment_filename': line.attachment_filename or (att.name if att else ''),
                'attachment_url': (
                    '%s/api/employee_warning/attachment/%s' % (base_url, att.id)
                    if att else ''
                ),
            })

        return {
            'has_warning': bool(warning.warning_line_ids),
            'warning_count': len(warning.warning_line_ids),
            'employee': {
                'code': warning.employee_code or '',
                'firstname': warning.firstname or '',
                'lastname': warning.lastname or '',
                'position': warning.position_id.name if warning.position_id else '',
                'branch': warning.branch_id.name if warning.branch_id else '',
                'department': warning.department_id.name if warning.department_id else '',
            },
            'lines': lines,
        }

    @api.model
    def api_get_warning_count(self, employee_code):
        """คืนค่าจำนวนใบเตือนทั้งหมดของพนักงาน (เร็วกว่า api_get_warnings_by_employee_code)"""
        if not employee_code:
            return 0
        warning = self.search([
            ('employee_code', '=', employee_code),
        ], limit=1)
        if not warning:
            return 0
        return len(warning.warning_line_ids)
