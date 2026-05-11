# -*- coding: utf-8 -*-
import json
import logging
import base64
from odoo import http, SUPERUSER_ID
from odoo.http import request, Response
from odoo.api import Environment

_logger = logging.getLogger(__name__)


class EmployeeInfoController(http.Controller):

    @http.route('/api/employee_info', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_employee_info(self, **kwargs):
        """
        API endpoint สำหรับดึงข้อมูลพนักงานจาก employee_code
        ใช้สำหรับ Flutter HRMS App
        URL: /api/employee_info?employee_code=XXX
        """
        employee_code = kwargs.get('employee_code')

        if not employee_code:
            return Response(
                json.dumps({'status': 'error', 'message': 'กรุณาระบุ employee_code'}, ensure_ascii=False),
                content_type='application/json; charset=utf-8',
                status=400
            )

        try:
            # ใช้ sudo() เพราะ auth='none'
            employee = request.env['employee.salary'].sudo().search(
                [('employee_code', '=', str(employee_code))],
                limit=1
            )

            if not employee:
                return Response(
                    json.dumps({'status': 'error', 'message': 'ไม่พบข้อมูลพนักงาน'}, ensure_ascii=False),
                    content_type='application/json; charset=utf-8',
                    status=404
                )

            # เตรียมข้อมูลที่จะส่งกลับ
            data = {
                'status': 'success',
                'data': {
                    # ข้อมูลส่วนตัว
                    'employee_code': employee.employee_code or '',
                    'prefix_th': employee.prefix_th or '',
                    'firstname': employee.firstname or '',
                    'lastname': employee.lastname or '',
                    'nickname': employee.nickname or '',
                    'firstname_eng': employee.firstname_eng or '',
                    'lastname_eng': employee.lastname_eng or '',
                    'gender': employee.gender or '',
                    'nationality': employee.nationality or '',
                    'birthdate': employee.birthdate.isoformat() if employee.birthdate else '',
                    'age': employee.age or 0,
                    'phone_number': employee.phone_number or '',
                    'email': employee.email or '',
                    'marital_status': employee.marital_status or '',

                    # ข้อมูลองค์กร
                    'company': employee.company or '',
                    'branch': employee.branch_id.name if employee.branch_id else '',
                    'department': employee.department_id.name if employee.department_id else '',
                    'position': employee.position_id.name if employee.position_id else '',
                    'employee_type': employee.employee_type or '',

                    # ข้อมูลการเงิน
                    'salary': employee.salary or 0.0,
                    'cost_of_living': employee.cost_of_living or 0.0,
                    'position_allowance': employee.position_allowance or 0.0,
                    'experience_allowance': employee.experience_allowance or 0.0,
                    'professional_allowance': employee.professional_allowance or 0.0,
                    'advance_payment_limit': employee.advance_payment_limit or 0.0,

                    # ข้อมูลการทำงาน
                    'start_date': employee.start_date.isoformat() if employee.start_date else '',
                    'appointment_date': employee.appointment_date.isoformat() if employee.appointment_date else '',
                    'contract_end_date': employee.contract_end_date.isoformat() if employee.contract_end_date else '',
                    'end_trial_date': employee.end_trial_date.isoformat() if employee.end_trial_date else '',
                    'probation_period': employee.probation_period or 0,

                    # สถานะ
                    'status': employee.status or '',
                }
            }

            return Response(
                json.dumps(data, ensure_ascii=False),
                content_type='application/json; charset=utf-8',
                status=200
            )

        except Exception as e:
            _logger.error("Error fetching employee info: %s", str(e))
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False),
                content_type='application/json; charset=utf-8',
                status=500
            )

    # ===== API ทวิ 50 =====

    @http.route('/api/wt_cert_list', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_wt_cert_list(self, **kwargs):
        """
        ดึงรายการหนังสือรับรองภาษีหัก ณ ที่จ่าย (ทวิ50) ของพนักงาน
        URL: /api/wt_cert_list?employee_code=XXX
        """
        employee_code = kwargs.get('employee_code')
        if not employee_code:
            return Response(
                json.dumps({'status': 'error', 'message': 'กรุณาระบุ employee_code'}, ensure_ascii=False),
                content_type='application/json; charset=utf-8', status=400
            )

        try:
            employee = request.env['employee.salary'].sudo().search(
                [('employee_code', '=', str(employee_code))], limit=1
            )
            if not employee:
                return Response(
                    json.dumps({'status': 'error', 'message': 'ไม่พบข้อมูลพนักงาน'}, ensure_ascii=False),
                    content_type='application/json; charset=utf-8', status=404
                )

            certs = request.env['hr.withholding.tax.cert'].sudo().search(
                [('employee_id', '=', employee.id), ('state', '=', 'done')],
                order='report_year desc'
            )

            cert_list = []
            for cert in certs:
                lines = []
                for line in cert.wt_line:
                    lines.append({
                        'income_type': line.wt_cert_income_type or '',
                        'income_desc': line.wt_cert_income_desc or '',
                        'base': line.base or 0.0,
                        'wt_percent': line.wt_percent or 0.0,
                        'amount': line.amount or 0.0,
                    })

                cert_list.append({
                    'id': cert.id,
                    'name': cert.name or '',
                    'report_year': cert.report_year or '',
                    'date': cert.date.isoformat() if cert.date else '',
                    'state': cert.state or '',
                    'company_name': cert.company_name or '',
                    'company_taxid': cert.company_taxid or '',
                    'employee_taxid': cert.employee_taxid or '',
                    'income_tax_form': cert.income_tax_form or '',
                    'total_net_salary': cert.total_net_salary or 0.0,
                    'lines': lines,
                })

            return Response(
                json.dumps({'status': 'success', 'data': cert_list}, ensure_ascii=False),
                content_type='application/json; charset=utf-8', status=200
            )

        except Exception as e:
            _logger.error("Error fetching wt cert list: %s", str(e))
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False),
                content_type='application/json; charset=utf-8', status=500
            )

    @http.route('/api/wt_cert_pdf', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_wt_cert_pdf(self, **kwargs):
        """
        ดาวน์โหลด PDF ทวิ50
        URL: /api/wt_cert_pdf?cert_id=XXX
        """
        cert_id = kwargs.get('cert_id')
        if not cert_id:
            return Response(
                json.dumps({'status': 'error', 'message': 'กรุณาระบุ cert_id'}, ensure_ascii=False),
                content_type='application/json; charset=utf-8', status=400
            )

        try:
            import odoo
            # สร้าง environment ใหม่ด้วย new cursor + SUPERUSER
            registry = odoo.registry(request.db)
            pdf_bytes = None
            filename = 'WT_Cert.pdf'

            cr = registry.cursor()
            try:
                env = Environment(cr, SUPERUSER_ID, {})
                cert = env['hr.withholding.tax.cert'].browse(int(cert_id))
                if not cert.exists():
                    cr.close()
                    return Response(
                        json.dumps({'status': 'error', 'message': 'ไม่พบเอกสารทวิ50'}, ensure_ascii=False),
                        content_type='application/json; charset=utf-8', status=404
                    )

                filename = 'WT_Cert_%s_%s.pdf' % (cert.employee_firstname or '', cert.report_year or '')

                # สร้าง PDF จาก report template
                report = env.ref('npd_hr_wt_cert_form.hr_wt_cert_pdf_report')
                pdf_content, pdf_type = report._render_qweb_pdf([cert.id])
                # เก็บ copy ของ bytes ก่อนปิด cursor
                pdf_bytes = bytes(pdf_content)
            finally:
                cr.close()

            if not pdf_bytes:
                return Response(
                    json.dumps({'status': 'error', 'message': 'ไม่สามารถสร้าง PDF ได้'}, ensure_ascii=False),
                    content_type='application/json; charset=utf-8', status=500
                )

            _logger.info("PDF generated: %s, size=%d bytes", filename, len(pdf_bytes))

            # ส่ง PDF เป็น base64 JSON เพื่อหลีกเลี่ยงปัญหา HTTP/1.0
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            return Response(
                json.dumps({
                    'status': 'success',
                    'filename': filename,
                    'pdf_base64': pdf_base64,
                }),
                content_type='application/json; charset=utf-8',
                status=200
            )

        except Exception as e:
            _logger.error("Error generating wt cert PDF: %s", str(e))
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False),
                content_type='application/json; charset=utf-8', status=500
            )

    # ===== API ตารางงาน (Work Schedule) =====

    @http.route('/api/work_schedule', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_work_schedule(self, **kwargs):
        """
        ดึงตารางงานของพนักงาน สำหรับตั้งแจ้งเตือนเข้า-ออกงาน
        URL: /api/work_schedule?employee_code=XXX
        """
        employee_code = kwargs.get('employee_code')
        if not employee_code:
            return Response(
                json.dumps({'status': 'error', 'message': 'กรุณาระบุ employee_code'}, ensure_ascii=False),
                content_type='application/json; charset=utf-8', status=400
            )

        try:
            employee = request.env['employee.salary'].sudo().search(
                [('employee_code', '=', str(employee_code))], limit=1
            )
            if not employee:
                return Response(
                    json.dumps({'status': 'error', 'message': 'ไม่พบข้อมูลพนักงาน'}, ensure_ascii=False),
                    content_type='application/json; charset=utf-8', status=404
                )

            schedule = request.env['hr.work.schedule'].sudo().search(
                [('employee_id', '=', employee.id)], limit=1
            )

            if not schedule:
                return Response(
                    json.dumps({'status': 'error', 'message': 'ไม่พบตารางงาน'}, ensure_ascii=False),
                    content_type='application/json; charset=utf-8', status=404
                )

            # แปลง float เวลา 8.5 → "08:30"
            def float_to_time(f):
                h = int(f)
                m = int((f - h) * 60)
                return '%02d:%02d' % (h, m)

            days = []
            day_map = [
                ('mon', 1, schedule.work_mon, schedule.mon_shift_start, schedule.mon_shift_end),
                ('tue', 2, schedule.work_tue, schedule.tue_shift_start, schedule.tue_shift_end),
                ('wed', 3, schedule.work_wed, schedule.wed_shift_start, schedule.wed_shift_end),
                ('thu', 4, schedule.work_thu, schedule.thu_shift_start, schedule.thu_shift_end),
                ('fri', 5, schedule.work_fri, schedule.fri_shift_start, schedule.fri_shift_end),
                ('sat', 6, schedule.work_sat, schedule.sat_shift_start, schedule.sat_shift_end),
            ]

            for day_code, weekday, is_work, start, end in day_map:
                if is_work:
                    days.append({
                        'day': day_code,
                        'weekday': weekday,  # 1=จันทร์ ... 7=อาทิตย์ (ISO)
                        'shift_start': float_to_time(start),
                        'shift_end': float_to_time(end),
                        'shift_start_float': start,
                        'shift_end_float': end,
                    })

            data = {
                'status': 'success',
                'data': {
                    'employee_code': employee.employee_code or '',
                    'category': schedule.category or '',
                    'days': days,
                }
            }

            return Response(
                json.dumps(data, ensure_ascii=False),
                content_type='application/json; charset=utf-8', status=200
            )

        except Exception as e:
            _logger.error("Error fetching work schedule: %s", str(e))
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False),
                content_type='application/json; charset=utf-8', status=500
            )