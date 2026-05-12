# -*- coding: utf-8 -*-

import requests
import json
import threading
from odoo import models, fields, api, _
from odoo import registry as odoo_registry
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import datetime
import math
import logging
import calendar
from datetime import date

_logger = logging.getLogger(__name__)

# URL ของ PHP API
LATENESS_API_URL = "https://npdhrms.com/calculate_lateness.php"
PHP_API_URL = "https://npdhrms.com/api.php"
PAYSLIP_API_URL = "https://npdhrms.com/api/get_payslip_data.php"


def round_half_up(n):
    """ ปัดเศษ .5 ขึ้น ต่ำกว่า .5 ลง """
    return int(n + 0.5)

class PayrollSalary(models.Model):
    _name = "payroll.salary"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "ทำเงินเดือน"

    _sql_constraints = [
        ('employee_month_year_uniq',
         'unique(employee_id, month, year)',
         'ไม่สามารถสร้างรายการเงินเดือนซ้ำสำหรับพนักงานคนเดิมในเดือนและปีเดียวกันได้!')
    ]

    def _get_thai_month_name(self, month):
        """แปลงเลขเดือน → ชื่อเดือนไทย"""
        months = {
            1: 'มกราคม', 2: 'กุมภาพันธ์', 3: 'มีนาคม', 4: 'เมษายน',
            5: 'พฤษภาคม', 6: 'มิถุนายน', 7: 'กรกฎาคม', 8: 'สิงหาคม',
            9: 'กันยายน', 10: 'ตุลาคม', 11: 'พฤศจิกายน', 12: 'ธันวาคม',
        }
        try:
            return months.get(int(month), '')
        except (ValueError, TypeError):
            return ''

    def _fmt_money(self, amount):
        """จัดรูปแบบตัวเลขเป็น 1,234.56"""
        try:
            return "{:,.2f}".format(float(amount or 0))
        except (ValueError, TypeError):
            return "0.00"

    def _get_payslip_company_info(self):
        """
        คืน dict ของชื่อ/ที่อยู่บริษัทตาม company ของพนักงาน
        (ตรงกับ getCompanyInfo ในแอป Flutter)
        """
        self.ensure_one()
        company = self.employee_id.company if self.employee_id else None
        mapping = {
            'นภดลเอสกรุ๊ปจำกัด': {
                'name': 'บริษัท นภดล เอส กรุ๊ป จำกัด',
                'address': 'ที่อยู่ 156 แขวงบางยี่ขัน เขตบางพลัด กรุงเทพมหานคร 10700  โทร. / แฟกซ์. 02-433-5556',
            },
            'เอ็นพีดีสตีลเทคจำกัด': {
                'name': 'บริษัท เอ็นพีดี สตีลเทค จำกัด',
                'address': 'ที่อยู่ 47/4 หมู่ 2 ตำบลลาดหลุมแก้ว อำเภอลาดหลุมแก้ว จังหวัดปทุมธานี 12140  โทร. / แฟกซ์. 02-433-5556',
            },
            'เอ็นพีดีโลจิสติกส์จำกัด': {
                'name': 'บริษัท เอ็นพีดี โลจิสติกส์ จำกัด',
                'address': 'ที่อยู่ 47/4 หมู่ 2 ตำบลลาดหลุมแก้ว อำเภอลาดหลุมแก้ว จังหวัดปทุมธานี 12140  โทร. / แฟกซ์. 02-433-5556',
            },
            'นภดลอินเตอร์เทรดดิ้งจำกัด': {
                'name': 'บริษัท นภดล อินเตอร์เทรดดิ้ง จำกัด',
                'address': 'ที่อยู่ 154 แขวงบางยี่ขัน เขตบางพลัด กรุงเทพมหานคร 10700  โทร. / แฟกซ์. 02-433-5556',
            },
            'นภดลกรุงเทพจำกัด': {
                'name': 'บริษัท นภดล กรุงเทพ จำกัด',
                'address': 'ที่อยู่ 36/10 หมู่ 2 ตำบลบางเตย อำเภอสามพราน จังหวัดนครปฐม 73210  โทร. / แฟกซ์. 02-433-5556',
            },
        }
        return mapping.get(company, {
            'name': 'บริษัท นภดล เอส กรุ๊ป จำกัด',
            'address': 'ที่อยู่ 156 แขวงบางยี่ขัน เขตบางพลัด กรุงเทพมหานคร 10700  โทร. / แฟกซ์. 02-433-5556',
        })

    def _get_payslip_api_data(self):
        """
        เรียก API https://npdhrms.com/api/get_payslip_data.php
        แล้วกรองเฉพาะของ month/year ของ payroll นี้
        คืน dict ว่างถ้า error หรือไม่เจอข้อมูล → template จะ fallback เป็นค่าจาก Odoo
        """
        self.ensure_one()
        if not self.employee_code:
            return {}

        try:
            payload = {'employee_code': self.employee_code}
            response = requests.post(
                PAYSLIP_API_URL,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=15
            )
            response.raise_for_status()
            api_response = response.json()

            if api_response.get('status') != 'success':
                _logger.warning("[PAYSLIP API] %s", api_response.get('message'))
                return {}

            data_list = api_response.get('data') or []
            # หา record ที่ตรงกับเดือน/ปีของ payroll นี้
            for item in data_list:
                if (str(item.get('month')) == str(self.month)
                        and str(item.get('year')) == str(self.year)):
                    _logger.info("[PAYSLIP API] Matched %s/%s for emp=%s",
                                 self.month, self.year, self.employee_code)
                    return item

            _logger.info("[PAYSLIP API] Not found %s/%s for emp=%s",
                         self.month, self.year, self.employee_code)
            return {}

        except requests.exceptions.RequestException as e:
            _logger.error("[PAYSLIP API] Request error: %s", e)
            return {}
        except Exception as e:
            _logger.exception("[PAYSLIP API] Unexpected error: %s", e)
            return {}

    def action_print_payslip(self):
        """เปิด Report พิมพ์สลิปเงินเดือน"""
        self.ensure_one()
        return self.env.ref('employee_salary.action_report_payslip').report_action(self)

    def action_open_lateness_summary(self):
        self.ensure_one()
        emp_code = self.employee_code
        month = self.month
        year = self.year
        cutoff_day = self.cutoff_day
        grace = self.lateness_grace_period  # ✅ เวลาสายไม่เกิน (นาที)

        # ✅ ดึง work schedule ของพนักงาน
        work_schedule = self.env['hr.work.schedule'].search([('employee_id', '=', self.employee_id.id)], limit=1)

        # ✅ map กะการทำงานไปเป็น dict
        schedule_data = {}
        if work_schedule:
            schedule_data = {
                'mon': f"{work_schedule.mon_shift_start}-{work_schedule.mon_shift_end}" if work_schedule.work_mon else "0-0",
                'tue': f"{work_schedule.tue_shift_start}-{work_schedule.tue_shift_end}" if work_schedule.work_tue else "0-0",
                'wed': f"{work_schedule.wed_shift_start}-{work_schedule.wed_shift_end}" if work_schedule.work_wed else "0-0",
                'thu': f"{work_schedule.thu_shift_start}-{work_schedule.thu_shift_end}" if work_schedule.work_thu else "0-0",
                'fri': f"{work_schedule.fri_shift_start}-{work_schedule.fri_shift_end}" if work_schedule.work_fri else "0-0",
                'sat': f"{work_schedule.sat_shift_start}-{work_schedule.sat_shift_end}" if work_schedule.work_sat else "0-0",
                'sun': "0-0",
            }

        # ✅ encode schedule เป็น JSON + urlencode
        import urllib.parse, json
        schedule_str = urllib.parse.quote(json.dumps(schedule_data))

        base_url = "https://npdhrms.com/lateness_summary.php"
        full_url = (
            f"{base_url}?employee_code={emp_code}"
            f"&month={month}&year={year}&cutoff_day={cutoff_day}"
            f"&lateness_grace_period={grace}"  # ✅ ส่งค่า grace period
            f"&work_schedule={schedule_str}"  # ✅ ส่งตารางกะไปด้วย
        )

        return {
            "type": "ir.actions.act_url",
            "url": full_url,
            "target": "new",  # เปิดแท็บใหม่
        }

    def _get_default_tax_brackets(self):
        return [
            (0, 0, {'sequence': 1, 'income_from': 0, 'income_to': 150000, 'rate': 0, 'deduction': 0}),
            (0, 0, {'sequence': 2, 'income_from': 150001, 'income_to': 300000, 'rate': 5, 'deduction': 7500}),
            (0, 0, {'sequence': 3, 'income_from': 300001, 'income_to': 500000, 'rate': 10, 'deduction': 22500}),
            (0, 0, {'sequence': 4, 'income_from': 500001, 'income_to': 750000, 'rate': 15, 'deduction': 47500}),
            (0, 0, {'sequence': 5, 'income_from': 750001, 'income_to': 1000000, 'rate': 20, 'deduction': 85000}),
            (0, 0, {'sequence': 6, 'income_from': 1000001, 'income_to': 2000000, 'rate': 25, 'deduction': 135000}),
            (0, 0, {'sequence': 7, 'income_from': 2000001, 'income_to': 5000000, 'rate': 30, 'deduction': 235000}),
            (0, 0, {'sequence': 8, 'income_from': 5000001, 'income_to': 999999999, 'rate': 35, 'deduction': 485000}),
        ]

    period_id = fields.Many2one('payroll.period', string='รอบเงินเดือน', ondelete='set null')
    active = fields.Boolean(default=True, index=True)
    employee_id = fields.Many2one('employee.salary', string='ชื่อพนักงาน', required=True)
    employee_code = fields.Char(string='รหัสพนักงาน', related='employee_id.employee_code', readonly=True)
    branch_id = fields.Many2one('hr.branch.custom', string='สาขา', related='employee_id.branch_id', store=True, readonly=True)
    firstname = fields.Char(string='ชื่อ', related='employee_id.firstname', store=True, readonly=True)
    lastname = fields.Char(string='นามสกุล', related='employee_id.lastname', store=True, readonly=True)
    base_salary = fields.Float(string="ฐานเงินเดือน", related='employee_id.salary', store=True, readonly=True)
    month = fields.Integer(string="เดือน", required=True, default=lambda self: fields.Date.today().month)
    year = fields.Char(string="ปี", required=True, default=lambda self: fields.Date.today().year)
    sso_rate = fields.Float(string="อัตราประกันสังคม (%)", default=5.0)
    sso_min_wage = fields.Float(string="ฐานเงินเดือนขั้นต่ำ (ประกันสังคม)", default=1650.0)
    sso_max_wage = fields.Float(string="ฐานเงินเดือนสูงสุด (ประกันสังคม)", default=17500.0)
    expense_deduction = fields.Float(string="ค่าใช้จ่าย (สูงสุด 100,000)", default=100000.0)
    personal_deduction = fields.Float(string="ค่าลดหย่อนส่วนตัว", default=60000.0)
    provident_fund_rate = fields.Float(string="อัตรากองทุนสำรองเลี้ยงชีพ (%)", default=0.0)
    provident_fund_deduction_max = fields.Float(string="หักกองทุนฯ สูงสุดไม่เกิน", default=500000.0)
    tax_bracket_ids = fields.One2many('payroll.tax.bracket', 'payroll_id', string='ขั้นบันไดอัตราภาษี',
                                      default=_get_default_tax_brackets)
    tax_monthly = fields.Float(
        string="ภาษีหัก ณ ที่จ่าย",
        compute="_compute_tax",
        inverse="_inverse_tax_monthly",
        store=True
    )
    tax_annual = fields.Float(string="ประมาณการภาษี (ต่อปี)", compute='_compute_tax', store=True)
    ot_api_url = fields.Char(string="API URL สำหรับข้อมูล OT", default="https://npdhrms.com/get_ot_data.php")
    # ot_rate_weekday = fields.Float(string="อัตรา OT วันธรรมดา", default=1.5)
    # ot_rate_holiday = fields.Float(string="อัตรา OT วันหยุด", default=2.0)
    ot_line_ids = fields.One2many('payroll.ot.line', 'payroll_id', string='รายการ OT')
    # รวมยอดแยกจาก OT Line
    ot_total_weekday = fields.Float(string="ค่าล่วงเวลา/โอที", compute='_compute_ot_totals', store=True)
    ot_total_holiday = fields.Float(string="ค่าล่วงเวลา/วันหยุดนักขัตฤกษ์", compute='_compute_ot_totals', store=True)
    ot_total_sunday = fields.Float(string="ค่าล่วงเวลา", compute='_compute_ot_totals', store=True)
    ot_total = fields.Float(string="ค่าล่วงเวลา รวม", compute='_compute_ot_totals', store=True)

    ot_calculation_method = fields.Selection([
        ('round_down', 'ปัดเศษเป็นชั่วโมงเต็ม'),
        ('actual', 'คำนวณตามจริง')
    ], string="วิธีการคำนวณชั่วโมง OT", default='round_down', required=True)
    ot_line_ids = fields.One2many('payroll.ot.line', 'payroll_id', string='รายการ OT')
    line_ids = fields.One2many("payroll.salary.line", "payroll_id", string="รายละเอียดเงินเดือน")
    
    # ✅ เพิ่ม flag สำหรับ override ยอดรวม
    override_totals = fields.Boolean(string="ปรับแก้ยอดรวมด้วยมือ", default=False)

    # ✅ ยอดรวม "เงินได้อื่นๆ" จากเมนู other.income ของเดือนเดียวกันกับ payment_date
    other_income_total = fields.Float(
        string="เงินได้อื่นๆ",
        compute="_compute_other_income_total",
        store=True,
        readonly=True,
        help="ยอดรวมเงินได้อื่นๆ ที่ยืนยันแล้ว และวันที่จ่ายเงินอยู่ในเดือนเดียวกับวันที่จ่ายเงินในรายการเงินเดือนนี้",
    )

    total_gross = fields.Float(
        string="รวมรายได้", 
        compute="_compute_total", 
        inverse="_inverse_total_gross",
        store=True
    )
    total_deduction = fields.Float(
        string="รวมรายการหัก", 
        compute="_compute_total", 
        inverse="_inverse_total_deduction",
        store=True
    )
    net_salary = fields.Float(
        string="เงินสุทธิ", 
        compute="_compute_total", 
        inverse="_inverse_net_salary",
        store=True
    )
    holiday_template_year = fields.Char(string="ปีของเทมเพลตวันหยุด", compute="_compute_holiday_template",
                                        store=True)
    lateness_api_url = fields.Char(string="API URL สำหรับขาดลามาสาย",
                                   default="https://npdhrms.com/calculate_lateness.php")
    lateness_grace_period = fields.Integer(string='เวลาสายไม่เกิน (นาที)', default=15)

    late_checkin_minutes = fields.Float(string='รวมเวลาสาย (นาที)', readonly=True)
    early_checkout_minutes = fields.Float(string='รวมเวลาออกก่อนเวลา (นาที)', readonly=True)
    lateness_minutes = fields.Float(string='รวมเวลาขาดงาน (นาที)', readonly=True)
    missed_days = fields.Integer(string='จำนวนวันขาดงาน', readonly=True)
    late_checkin_deduction = fields.Float(string='ยอดหักสาย', readonly=True)
    early_checkout_deduction = fields.Float(string='ยอดหักออกก่อนเวลา', readonly=True)
    missed_days_deduction = fields.Float(string='ยอดหักขาดงาน', readonly=True)
    lateness_deduction = fields.Float(string='ยอดหักรวม', readonly=True)
    cutoff_day = fields.Integer(string='วันตัดรอบ', default=24, required=True)
    leave_deduction_total = fields.Float(string='ยอดหักจากการลา', readonly=True)

    ot_total = fields.Float(string="ค่าล่วงเวลา (OT) รวม", compute='_compute_summary_totals', store=True)
    sso_total = fields.Float(
        string="ประกันสังคม",
        compute="_compute_sso_total",
        inverse="_inverse_sso_total",  # ✅ เพิ่ม inverse
        store=True
    )
    payment_date = fields.Date(
        string="วันที่จ่ายเงิน",
        default=lambda self: self._get_default_date_28()
    )
    manual_override_accumulated = fields.Boolean(
        string="ปรับค่าสะสมเอง",
        default=False,
        help="เมื่อเปิดอยู่ ระบบจะไม่คำนวณค่าสะสมทับค่าที่ผู้ใช้ใส่เอง"
    )
    accumulated_income = fields.Float(
        string="รายรับสะสม",
        compute="_compute_accumulated_values",
        inverse="_inverse_accumulated_values",
        store=True
    )
    accumulated_vat = fields.Float(
        string="ภาษีสะสม",
        compute="_compute_accumulated_values",
        inverse="_inverse_accumulated_values",
        store=True
    )
    accumulated_social_security = fields.Float(
        string="ประกันสังคมสะสม",
        compute="_compute_accumulated_values",
        inverse="_inverse_accumulated_values",
        store=True
    )


    # รายได้เสริม (ดึงจาก employee.salary)
    income_cost_of_living = fields.Float(string="เงินค่าครองชีพ", related="employee_id.cost_of_living", store=True,
                                         readonly=True)
    income_position_allowance = fields.Float(string="เงินประจำตำแหน่ง", related="employee_id.position_allowance",
                                             store=True, readonly=True)
    income_experience_allowance = fields.Float(string="เงินค่าประสบการณ์", related="employee_id.experience_allowance",
                                               store=True, readonly=True)
    income_professional_allowance = fields.Float(string="เงินค่าวิชาชีพ", related="employee_id.professional_allowance",
                                                 store=True, readonly=True)
    # รายได้ใหม่
    income_allowance = fields.Float(string="เบี้ยเลี้ยง", default=0.0)
    income_food = fields.Float(string="ค่าอาหาร", default=0.0)
    income_transport = fields.Float(string="ค่าเดินทาง", default=0.0)
    income_fuel = fields.Float(string="อินเซนทีฟ", default=0.0)
    income_commission = fields.Float(string="ค่าคอมมิชชั่นสาขา", default=0.0)
    income_commission_sale = fields.Float(string="ค่าคอมมิชชั่นSale", default=0.0)
    income_other = fields.Float(string="รายได้อื่นๆ", default=0.0)

    # รายจ่ายใหม่
    expense_provident = fields.Float(string="กองทุนสำรองเลี้ยงชีพ", default=0.0)
    expense_advance = fields.Float(string="เบิกเงินล่วงหน้า", default=0.0)
    expense_loan = fields.Float(string="เงินกู้", default=0.0)
    expense_ksl = fields.Float(string="กยศ", default=0.0)
    expense_insurance = fields.Float(string="เงินประกันการทำงาน", default=0.0)
    expense_other = fields.Float(string="หักอื่นๆ", default=0.0)

    # แยก ขาด-ลา-สาย
    deduction_late = fields.Float(string="สาย", default=0.0)
    deduction_leave = fields.Float(string="ลากิจ", default=0.0)
    deduction_absent = fields.Float(string="ขาดงาน", default=0.0)
    manual_override = fields.Boolean(string="ปรับแก้ด้วยมือ", default=False)

    # ✅ ฟิลด์ใหม่ ใช้แทน manual_override (เฉพาะ OT)
    override_ot = fields.Boolean(string="ปรับแก้ OT ด้วยมือ", default=False)

    manual_ot_weekday = fields.Float(string="ค่าล่วงเวลา/โอที", default=0.0)
    manual_ot_holiday = fields.Float(string="ค่าล่วงเวลา/วันหยุดนักขัตฤกษ์", default=0.0)
    manual_ot_sunday = fields.Float(string="ค่าล่วงเวลา", default=0.0)

    def _inverse_tax_monthly(self):
        """ให้ user แก้ tax_monthly ได้ตรง ๆ"""
        for rec in self:
            # sync ค่าแก้ไขไปยัง line_ids
            line = rec.line_ids.filtered(lambda l: l.name == 'ภาษีหัก ณ ที่จ่าย')
            if line:
                line.amount = rec.tax_monthly
            else:
                rec.line_ids = [(0, 0, {
                    'name': 'ภาษีหัก ณ ที่จ่าย',
                    'type': 'deduction',
                    'amount': rec.tax_monthly
                })]

    @api.depends('line_ids.amount', 'line_ids.name')
    def _compute_sso_total(self):
        for rec in self:
            rec.sso_total = sum(l.amount for l in rec.line_ids if l.name == 'ประกันสังคม')

    def _inverse_sso_total(self):
        """ ให้แก้ sso_total ได้ตรง ๆ """
        for rec in self:
            # ถ้ามี line 'ประกันสังคม' อยู่แล้ว → update ค่าใหม่
            line = rec.line_ids.filtered(lambda l: l.name == 'ประกันสังคม')
            if line:
                line.amount = rec.sso_total
            else:
                # ถ้าไม่มี → เพิ่ม line ใหม่เข้าไป
                rec.line_ids = [(0, 0, {
                    'name': 'ประกันสังคม',
                    'type': 'deduction',
                    'amount': rec.sso_total
                })]

    @api.onchange('manual_ot_weekday', 'manual_ot_holiday', 'manual_ot_sunday')
    def _onchange_manual_ot(self):
        """ ถ้า user แก้ค่า OT ด้วยมือ → update line_ids ด้วย """
        for rec in self:
            if rec.override_ot:
                _logger.info("[MANUAL OT OVERRIDE] Trigger update lines for payroll %s", rec.id)

                for line in rec.line_ids:
                    if line.name == 'ค่าล่วงเวลา/โอที':
                        line.amount = rec.manual_ot_weekday
                    elif line.name == 'ค่าล่วงเวลา/วันหยุดนักขัตฤกษ์':
                        line.amount = rec.manual_ot_holiday
                    elif line.name == 'ค่าล่วงเวลา':
                        line.amount = rec.manual_ot_sunday

                rec._compute_total()

    @api.depends('ot_line_ids.ot_amount', 'ot_line_ids.ot_type')
    def _compute_ot_totals(self):
        for rec in self:
            weekday, holiday, sunday = 0, 0, 0
            for line in rec.ot_line_ids:
                if line.ot_type == 'weekday':
                    weekday += line.ot_amount
                elif line.ot_type == 'holiday':
                    holiday += line.ot_amount
                elif line.ot_type == 'sunday':
                    sunday += line.ot_amount

            rec.ot_total_weekday = weekday
            rec.ot_total_holiday = holiday
            rec.ot_total_sunday = sunday

            # 🟢 sync ค่าจาก ot_line_ids → manual_ot_* เสมอ
            # - override_ot=False: เห็นค่าจาก API ที่ดึงมา
            # - override_ot=True: user แก้แถว → manual_ot_* update ตาม → line_ids ใช้ค่าใหม่
            rec.manual_ot_weekday = weekday
            rec.manual_ot_holiday = holiday
            rec.manual_ot_sunday = sunday

            rec._populate_all_lines()


    # ฟังก์ชันคำนวณ — สะสมต่อเดือนภายในปีเดียวกัน, reset ทุกปีใหม่ (ม.ค.)
    @api.depends('employee_id', 'month', 'year', 'base_salary', 'tax_monthly', 'sso_total',
                 'manual_override_accumulated')
    def _compute_accumulated_values(self):
        for rec in self:
            # ถ้า user แก้ค่าเองแล้ว → ไม่คำนวณทับ
            if rec.manual_override_accumulated:
                continue

            base_salary = rec.base_salary or 0.0
            tax = rec.tax_monthly or 0.0
            sso = rec.sso_total or 0.0

            # หา record ของ "เดือนก่อนหน้าในปีเดียวกัน" เท่านั้น
            # → ม.ค. = ไม่เจอ prev → reset เริ่มใหม่
            prev = self.env['payroll.salary'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('year', '=', rec.year),
                ('month', '<', rec.month),
            ], order='month desc', limit=1)

            if prev:
                rec.accumulated_income = prev.accumulated_income + base_salary
                rec.accumulated_vat = prev.accumulated_vat + tax
                rec.accumulated_social_security = prev.accumulated_social_security + sso
            else:
                # เดือนแรกของปี (ม.ค.) → reset เริ่มใหม่
                rec.accumulated_income = base_salary
                rec.accumulated_vat = tax
                rec.accumulated_social_security = sso

    # ฟังก์ชัน inverse → ตั้ง flag ให้ compute ไม่ทับค่าที่ user แก้
    def _inverse_accumulated_values(self):
        for rec in self:
            _logger.info(
                "[INVERSE] Manual override EmpCode=%s | income=%s vat=%s sso=%s",
                rec.employee_id.employee_code if rec.employee_id else "-",
                rec.accumulated_income,
                rec.accumulated_vat,
                rec.accumulated_social_security
            )
            rec.manual_override_accumulated = True

    @api.model
    def _get_default_date_28(self):
        today = date.today()
        # ถ้าวันที่ปัจจุบัน < 28 ให้ใช้เดือนนี้, ถ้า >=28 ให้เลื่อนไปเดือนถัดไป
        if today.day < 28:
            return today.replace(day=28)
        else:
            # กรณีเป็นสิ้นเดือน เช่น ธันวา → ต้องข้ามไป ม.ค. ปีถัดไป
            if today.month == 12:
                return date(today.year + 1, 1, 28)
            else:
                return date(today.year, today.month + 1, 28)

    def _prepare_data_for_php(self):
        self.ensure_one()
        previous_payroll = self.env['payroll.salary'].search([
            ('employee_id', '=', self.employee_id.id),
            ('id', '!=', self.id)
        ], order='year DESC, month DESC', limit=1)

        accumulated_income = self.base_salary
        accumulated_vat = self.tax_monthly
        accumulated_social_security = self.sso_total

        if previous_payroll:
            accumulated_income += previous_payroll.accumulated_income
            accumulated_vat += previous_payroll.accumulated_vat
            accumulated_social_security += previous_payroll.accumulated_social_security

        payment_date_str = self.payment_date.strftime('%Y-%m-%d') if self.payment_date else None

        return {
            'odoo_id': self.id,
            'employee_id': self.employee_id.id,
            'employee_code': self.employee_code,
            'base_salary': self.base_salary,
            'month': self.month,
            'year': self.year,
            'total_gross': self.total_gross,
            'total_deduction': self.total_deduction,
            'net_salary': self.net_salary,
            # ✅ OT แยกประเภท
            'ot_total': self.ot_total,
            'ot_total_weekday': self.manual_ot_weekday if self.override_ot else self.ot_total_weekday,
            'ot_total_holiday': self.manual_ot_holiday if self.override_ot else self.ot_total_holiday,
            'ot_total_sunday': self.manual_ot_sunday if self.override_ot else self.ot_total_sunday,

            # ✅ ประกันสังคมและภาษี
            'sso_total': self.sso_total,
            'tax_monthly': self.tax_monthly,
            # ✅ หักสาย/ลา/ขาดงาน แยก + รวม
            'deduction_late': self.deduction_late,
            'deduction_leave': self.deduction_leave,
            'deduction_absent': self.deduction_absent,
            'late_checkin_deduction': self.late_checkin_deduction,
            'early_checkout_deduction': self.early_checkout_deduction,
            'missed_days_deduction': self.missed_days_deduction,

            'lateness_deduction': self.lateness_deduction,
            # ✅ รายได้เสริม
            'income_cost_of_living': self.income_cost_of_living,
            'income_position_allowance': self.income_position_allowance,
            'income_experience_allowance': self.income_experience_allowance,
            'income_professional_allowance': self.income_professional_allowance,
            'income_allowance': self.income_allowance,
            'income_food': self.income_food,
            'income_transport': self.income_transport,
            'income_fuel': self.income_fuel,
            'income_commission': self.income_commission,
            'income_commission_sale': self.income_commission_sale,
            'income_other': self.income_other,
            # ✅ รายจ่ายใหม่
            'expense_provident': self.expense_provident,
            'expense_advance': self.expense_advance,
            'expense_loan': self.expense_loan,
            'expense_ksl': self.expense_ksl,
            'expense_insurance': self.expense_insurance,
            'expense_other': self.expense_other,
            # ✅ provident fund rate-based
            'provident_fund_rate': self.provident_fund_rate,
            # ✅ ค่าที่สะสม
            'payment_date': payment_date_str,
            'accumulated_income': accumulated_income,
            'accumulated_vat': accumulated_vat,
            'accumulated_social_security': accumulated_social_security,
        }

    def _send_data_to_php_api(self, action, data):
        try:
            payload = {'action': action, 'data': data}
            headers = {'Content-Type': 'application/json'}
            response = requests.post(PHP_API_URL, data=json.dumps(payload), headers=headers, timeout=10)
            response.raise_for_status()
            api_response = response.json()
            if api_response.get('status') == 'success':
                _logger.info(f"Successfully sent {action} data to PHP API for record {data.get('odoo_id')}")
            else:
                _logger.error(f"Failed to send {action} data to PHP API: {api_response.get('message')}")
        except requests.exceptions.RequestException as e:
            _logger.error(f"API Connection Error: {e}")
        except json.JSONDecodeError:
            _logger.error("JSON Decode Error: Response from API is not a valid JSON.")

    @api.onchange('employee_id', 'ot_calculation_method', 'month', 'year')
    def _onchange_employee_id(self):
        if self.employee_id and self.month and self.year:
            # onchange ทำงานบน record ที่ยังไม่ save (NewId) → ใช้ sequential
            self._fetch_vehicle_booking_data()
            self._fetch_commission_branch_data()
            self._fetch_commission_sales_data()
            warning_dict = self._populate_all_lines()

            if warning_dict:
                return warning_dict
        else:
            self.line_ids = [(5, 0, 0)]
            self.ot_line_ids = [(5, 0, 0)]

    def _parallel_fetch_all(self):
        """
        ดึงข้อมูลจาก API 3 ตัว (vehicle booking, commission branch, commission sales)
        แบบ parallel ด้วย threading — แต่ละ thread มี cursor แยก safe สำหรับ ORM
        ใช้ใน create/write — ใช้ไม่ได้ตอน onchange (record ยังเป็น NewId)

        ลดเวลาจาก ~15-80 วิ → ~5-30 วิ (เท่า API ที่ช้าที่สุด)
        """
        self.ensure_one()

        # record ต้อง save แล้ว (มี id จริง) ถึงจะ parallel ได้
        if not self.id or isinstance(self.id, models.NewId):
            self._fetch_vehicle_booking_data()
            self._fetch_commission_branch_data()
            self._fetch_commission_sales_data()
            return

        db_name = self.env.cr.dbname
        uid = self.env.uid
        record_id = self.id

        def _run_in_thread(method_name):
            """รัน fetch method ใน cursor แยก"""
            try:
                with odoo_registry(db_name).cursor() as cr:
                    env = api.Environment(cr, uid, {})
                    rec = env['payroll.salary'].browse(record_id)
                    getattr(rec, method_name)()
                    cr.commit()
                    _logger.info("[PARALLEL] %s DONE for payroll %s", method_name, record_id)
            except Exception as e:
                _logger.exception("[PARALLEL] %s ERROR for payroll %s: %s",
                                  method_name, record_id, e)

        methods = [
            '_fetch_vehicle_booking_data',
            '_fetch_commission_branch_data',
            '_fetch_commission_sales_data',
        ]
        threads = []
        for m in methods:
            t = threading.Thread(target=_run_in_thread, args=(m,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=180)  # กันค้าง — timeout 3 นาที/thread

        # invalidate cache เพื่อให้ main thread เห็นค่าที่ thread อื่นเขียน
        self.invalidate_cache()


    def _get_previous_record(self):
        self.ensure_one()
        if not self.employee_code or not self.id:  # new record ยังไม่บันทึก
            return False
        return self.search([
            ('employee_code', '=', self.employee_code),
            ('id', '!=', self.id),
        ], order='id desc', limit=1)

    @api.onchange('deduction_late', 'deduction_leave', 'deduction_absent')
    def _onchange_manual_deductions(self):
        """
        เมื่อแก้ไขค่า หักสาย / หักลากิจ / หักขาดงาน ด้วยมือ
        ให้ update line_ids และคำนวณยอดใหม่ทันที
        """
        for rec in self:
            if rec.manual_override:
                _logger.info("[MANUAL OVERRIDE] Update manual deductions for payroll %s", rec.id)

                # อัพเดทลง line_ids ถ้ามีรายการอยู่แล้ว
                updated_lines = []
                for line in rec.line_ids:
                    if line.name == 'หักสาย':
                        line.amount = rec.deduction_late
                    elif line.name == 'หักลากิจ':
                        line.amount = rec.deduction_leave
                    elif line.name == 'หักขาดงาน':
                        line.amount = rec.deduction_absent
                    updated_lines.append(line)

                rec._compute_total()


    @api.model_create_multi
    def create(self, vals_list):
        records = super(PayrollSalary, self).create(vals_list)
        for record in records:
            # ✅ ดึงข้อมูล API แบบ parallel (เร็วกว่า serial ~3 เท่า)
            record._parallel_fetch_all()
            record._populate_all_lines()
            _logger.info(
                "[CREATE] Payroll created for %s | Month: %s/%s | income=%s, vat=%s, sso=%s",
                record.employee_id.firstname, record.month, record.year,
                record.accumulated_income, record.accumulated_vat, record.accumulated_social_security
            )
            data = record._prepare_data_for_php()
            record._send_data_to_php_api('create', data)
        return records

    def write(self, vals):
        res = super(PayrollSalary, self).write(vals)
        for record in self:
            if not record.manual_override:
                if any(f in vals for f in [
                    'employee_id', 'ot_calculation_method', 'month', 'year', 'cutoff_day',
                    'income_allowance', 'income_food', 'income_transport',
                    'income_fuel', 'income_commission', 'income_commission_sale', 'income_other',
                    'expense_provident', 'expense_advance', 'expense_loan',
                    'expense_ksl', 'expense_insurance', 'expense_other'
                ]):
                    record._populate_all_lines()

            _logger.info(
                "[WRITE] Payroll updated for %s | Month: %s/%s | income=%s, vat=%s, sso=%s",
                record.employee_id.firstname, record.month, record.year,
                record.accumulated_income, record.accumulated_vat, record.accumulated_social_security
            )
            data = record._prepare_data_for_php()
            record._send_data_to_php_api('update', data)
        return res

    @api.onchange(
        'income_allowance', 'income_food', 'income_transport',
        'income_fuel', 'income_commission', 'income_commission_sale', 'income_other',
        'expense_provident', 'expense_advance', 'expense_loan',
        'expense_ksl', 'expense_insurance', 'expense_other'
    )
    def _onchange_income_expense_fields(self):
        if self:
            self._populate_all_lines()

    def _get_sales_commission_rate(self, total_net_rental):
        """คำนวณอัตราคอมมิชชั่น Sales ตามขั้นบันได (ดึงจากเมนูตั้งค่า)"""
        configs = self.env['commission.rate.config'].search([], order='min_amount desc')
        for config in configs:
            if total_net_rental >= config.min_amount:
                return config.rate
        return 0.0

    def _fetch_vehicle_booking_data(self):
        """
        ดึงค่าเที่ยว (travel_expenses) และค่าเบี้ยเลี้ยง (daily_allowance)
        จาก API https://npd-solution.com/api/vehicle-booking
        กรองจาก ชื่อ+นามสกุล (driver_name), เดือน, ปี
        → เซ็ตลง income_transport และ income_allowance
        """
        self.ensure_one()

        if not self.employee_id or not self.month or not self.year:
            return

        import re
        emp_firstname = (self.firstname or '').strip()
        emp_lastname = (self.lastname or '').strip()
        # normalize ช่องว่างหลายตัวให้เหลือ 1 ตัว เพื่อเปรียบเทียบ
        emp_fullname = re.sub(r'\s+', ' ', (emp_firstname + ' ' + emp_lastname).strip())

        month = self.month
        year = str(self.year).strip()

        _logger.info("=" * 60)
        _logger.info("[VEHICLE BOOKING] เริ่มดึงข้อมูลค่าเที่ยว/เบี้ยเลี้ยง สำหรับ: '%s' | เดือน: %s/%s",
                     emp_fullname, month, year)

        login_url = 'https://npd-solution.com/web/session/authenticate'
        api_url = 'https://npd-solution.com/api/vehicle-booking'
        login_db = 'NPD_Logistics'
        login_user = 'Npd_admin'
        login_pass = '1234'

        total_travel_expenses = 0.0
        total_daily_allowance = 0.0

        try:
            # ===== Step 1: Login =====
            session = requests.Session()
            login_payload = {
                "jsonrpc": "2.0",
                "params": {
                    "db": login_db,
                    "login": login_user,
                    "password": login_pass
                }
            }
            login_resp = session.post(login_url, json=login_payload, timeout=30, verify=False)
            login_data = login_resp.json()

            if login_data.get('error'):
                _logger.warning("[VEHICLE BOOKING] Login FAILED | error=%s", login_data['error'])
                return

            _logger.info("[VEHICLE BOOKING] Login OK db=%s", login_db)

            # ===== Step 2: ดึงข้อมูล vehicle.booking =====
            api_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "month": month,
                    "year": int(year)
                }
            }
            api_resp = session.post(api_url, json=api_payload, timeout=60, verify=False)
            api_data = api_resp.json()

            result = api_data.get('result', {})
            if result.get('status') != 'success':
                _logger.warning("[VEHICLE BOOKING] API FAILED | result=%s", result)
                return

            data_list = result.get('data', [])
            _logger.info("[VEHICLE BOOKING] จำนวนข้อมูลทั้งหมด: %d", len(data_list))

            # ===== Log driver_name ทั้งหมดจาก API เพื่อ debug =====
            for idx, item in enumerate(data_list):
                _logger.info("[VEHICLE BOOKING] [%d] driver_name='%s' | booking=%s",
                             idx, item.get('driver_name', ''), item.get('name', ''))

            # ===== Step 3: กรองตาม driver_name (ชื่อ + นามสกุล) =====
            found = False
            for item in data_list:
                # normalize ช่องว่างหลายตัวให้เหลือ 1 ตัว ทั้ง 2 ฝั่ง
                api_driver_name = re.sub(r'\s+', ' ', (item.get('driver_name') or '').strip())

                if api_driver_name == emp_fullname:
                    travel_exp = item.get('travel_expenses', 0.0) or 0.0
                    daily_allow = item.get('daily_allowance', 0.0) or 0.0
                    total_travel_expenses += travel_exp
                    total_daily_allowance += daily_allow
                    found = True
                    _logger.info(
                        "[VEHICLE BOOKING] MATCH! driver=%s | booking=%s | travel=%.2f | allowance=%.2f",
                        api_driver_name, item.get('name', ''), travel_exp, daily_allow
                    )

            if not found:
                _logger.info("[VEHICLE BOOKING] ไม่พบข้อมูลที่ตรงกัน | ค้นหา: '%s'", emp_fullname)

        except Exception as e:
            _logger.exception("[VEHICLE BOOKING] ERROR | %s", str(e))
            return

        _logger.info("[VEHICLE BOOKING] ★★★ รวม travel_expenses=%.2f | daily_allowance=%.2f",
                     total_travel_expenses, total_daily_allowance)

        # ===== เซ็ตค่าลง field =====
        self.income_transport = total_travel_expenses
        self.income_allowance = total_daily_allowance

        _logger.info("[VEHICLE BOOKING] ✅ เซ็ต income_transport=%.2f | income_allowance=%.2f สำเร็จ",
                     self.income_transport, self.income_allowance)

    def _fetch_commission_sales_data(self):
        """
        ดึงค่าคอมมิชชั่น Sales จาก API https://npderp.com/api/commission/sales
        ทั้ง 3 db: NPD_Intertrading_New, NPD_S_Group_New_V2, NPD_Bangkok_New
        กรองจาก ชื่อ-นามสกุล, สาขา, เดือน/ปี
        รวม net_rental ทั้ง 3 db → เซ็ตลง income_commission_sale
        เรียกอัตโนมัติเมื่อเลือกพนักงาน/เปลี่ยนเดือน/ปี
        """
        self.ensure_one()

        if not self.employee_id or not self.month or not self.year:
            return

        # ชื่อ-นามสกุลของพนักงาน
        emp_firstname = (self.firstname or '').strip()
        emp_lastname = (self.lastname or '').strip()
        emp_fullname = (emp_firstname + ' ' + emp_lastname).strip()
        # ชื่อสาขา
        emp_branch_name = (self.branch_id.name or '').strip()
        # เดือน/ปี
        month = self.month
        year = str(self.year).strip()

        _logger.info("=" * 60)
        _logger.info("[COMMISSION SALES] เริ่มดึงค่าคอม Sales สำหรับ: %s | สาขา: %s | เดือน: %s/%s",
                     emp_fullname, emp_branch_name, month, year)

        # รายชื่อ database ที่ต้องดึง
        db_list = ['NPD_Intertrading_New', 'NPD_S_Group_New_V2', 'NPD_Bangkok_New']
        login_url = 'https://npderp.com/web/session/authenticate'
        commission_url = 'https://npderp.com/api/commission/sales'
        login_user = 'Npd_admin'
        login_pass = '1234'

        total_commission = 0.0

        for db_name in db_list:
            try:
                # ===== Step 1: Login =====
                session = requests.Session()
                login_payload = {
                    "jsonrpc": "2.0",
                    "params": {
                        "db": db_name,
                        "login": login_user,
                        "password": login_pass
                    }
                }
                login_resp = session.post(login_url, json=login_payload, timeout=30)
                login_data = login_resp.json()

                if login_data.get('error'):
                    _logger.warning("[COMMISSION SALES] Login FAILED db=%s | error=%s", db_name, login_data['error'])
                    continue

                _logger.info("[COMMISSION SALES] Login OK db=%s", db_name)

                # ===== Step 2: ดึงข้อมูลค่าคอม =====
                commission_payload = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "month": month,
                        "year": int(year)
                    }
                }
                comm_resp = session.post(commission_url, json=commission_payload, timeout=60)
                comm_data = comm_resp.json()

                result = comm_data.get('result', {})
                if result.get('status') != 'success':
                    _logger.warning("[COMMISSION SALES] API FAILED db=%s | result=%s", db_name, result)
                    continue

                data_list = result.get('data', [])
                _logger.info("[COMMISSION SALES] db=%s | จำนวนข้อมูลทั้งหมด: %d", db_name, len(data_list))

                # ===== Log รายชื่อทั้งหมดจาก API เพื่อ debug =====
                for idx, item in enumerate(data_list):
                    _logger.info(
                        "[COMMISSION SALES] db=%s | [%d] sales_contact_name='%s' | branch_name='%s' | net_rental=%.2f",
                        db_name, idx,
                        item.get('sales_contact_name', ''),
                        item.get('branch_name', ''),
                        item.get('net_rental', 0.0)
                    )

                # ===== Step 3: กรองข้อมูล (แค่ชื่อ รวมทุกสาขาของ Sales คนนั้น) =====
                db_net_rental = 0.0
                found = False
                for item in data_list:
                    api_sales_name = (item.get('sales_contact_name') or '').strip()
                    api_branch_name = (item.get('branch_name') or '').strip()

                    # เปรียบเทียบ ชื่อ-นามสกุล เท่านั้น (ไม่กรองสาขา เพราะ Sales ขายได้หลายสาขา)
                    name_match = (api_sales_name == emp_fullname)

                    if name_match:
                        net_rental = item.get('net_rental', 0.0)
                        db_net_rental += net_rental
                        found = True
                        _logger.info(
                            "[COMMISSION SALES] MATCH! db=%s | sales=%s | branch=%s | net_rental=%.2f",
                            db_name, api_sales_name, api_branch_name, net_rental
                        )

                if not found:
                    _logger.info("[COMMISSION SALES] ไม่พบข้อมูลที่ตรงกัน db=%s | ค้นหา: %s",
                                 db_name, emp_fullname)

                _logger.info("[COMMISSION SALES] ★ db=%s | net_rental รวม = %.2f", db_name, db_net_rental)
                total_commission += db_net_rental

            except Exception as e:
                _logger.exception("[COMMISSION SALES] ERROR db=%s | %s", db_name, str(e))
                continue

        _logger.info("[COMMISSION SALES] ★★★ ยอดรวม net_rental ทั้ง 3 db = %.2f", total_commission)

        # ===== ดึงยอด bankheaw (เฉพาะ NPD_S_Group_New_V2, type=เซลล์, กรองชื่อ) =====
        bankheaw_url = 'https://npderp.com/api/commission/bankheaw'
        bankheaw_db = 'NPD_S_Group_New_V2'

        try:
            session = requests.Session()
            login_payload = {
                "jsonrpc": "2.0",
                "params": {"db": bankheaw_db, "login": login_user, "password": login_pass}
            }
            login_resp = session.post(login_url, json=login_payload, timeout=30)
            login_data = login_resp.json()

            if not login_data.get('error'):
                bk_payload = {
                    "jsonrpc": "2.0", "method": "call",
                    "params": {"month": month, "year": int(year)}
                }
                bk_resp = session.post(bankheaw_url, json=bk_payload, timeout=60)
                bk_data = bk_resp.json()

                result_bk = bk_data.get('result', {})
                if result_bk.get('status') == 'success':
                    for item in result_bk.get('data', []):
                        if item.get('sort_order', 0) != 0:
                            continue
                        item_type = (item.get('type') or '').strip()
                        if item_type != 'เซลล์':
                            continue
                        api_sales_name = (item.get('salesperson_name') or '').strip()
                        if emp_fullname and emp_fullname in api_sales_name:
                            net = item.get('net_total', 0.0)
                            total_commission += net
                            _logger.info("[COMMISSION SALES - BANKHEAW] MATCH! sales=%s | net_total=%.2f",
                                         api_sales_name, net)

        except Exception as e:
            _logger.exception("[COMMISSION SALES - BANKHEAW] ERROR | %s", str(e))

        _logger.info("=" * 60)
        _logger.info("[COMMISSION SALES] ★★★ ยอดรวม net_rental (รวม bankheaw) = %.2f", total_commission)

        # คำนวณอัตราคอมมิชชั่นตามขั้นบันได
        rate = self._get_sales_commission_rate(total_commission)
        commission_amount = total_commission * (rate / 100.0)

        _logger.info("[COMMISSION SALES] ★★★ อัตรา = %.2f%% | ค่าคอม = %.2f x %.2f%% = %.2f",
                     rate, total_commission, rate, commission_amount)
        _logger.info("=" * 60)

        # เซ็ตค่าลง field ค่าคอมมิชชั่นSale (ยอดที่คิด % แล้ว)
        self.income_commission_sale = commission_amount

    def _fetch_commission_branch_data(self):
        """
        ดึงค่าคอมมิชชั่นสาขา จาก API https://npderp.com/api/commission/branch
        ทั้ง 3 db: NPD_Intertrading_New, NPD_S_Group_New_V2, NPD_Bangkok_New
        กรองจาก ชื่อสาขา, เดือน/ปี
        รวม net_rental ทั้ง 3 db แล้ว หารด้วยจำนวนพนักงาน active ในสาขาเดียวกัน
        → เซ็ตลง income_commission
        """
        self.ensure_one()

        if not self.employee_id or not self.month or not self.year:
            return

        # ชื่อสาขาจากพนักงาน
        emp_branch_name = (self.branch_id.name or '').strip()
        if not emp_branch_name:
            _logger.info("[COMMISSION BRANCH] พนักงานไม่มีสาขา ข้าม")
            return

        month = self.month
        year = str(self.year).strip()

        _logger.info("=" * 60)
        _logger.info("[COMMISSION BRANCH] เริ่มดึงค่าคอมสาขา | สาขา: %s | เดือน: %s/%s",
                     emp_branch_name, month, year)

        # ดึงพนักงาน active ทั้งหมดในสาขา + คำนวณสัดส่วนตามตำแหน่ง
        active_employees = self.env['employee.salary'].search([
            ('branch_id', '=', self.branch_id.id),
            ('status', '=', 'active'),
        ])
        if not active_employees:
            _logger.warning("[COMMISSION BRANCH] ไม่มีพนักงาน active ในสาขา ข้าม")
            return

        # คำนวณสัดส่วนจากตารางตั้งค่าคอมมิชชั่นสาขา (รายพนักงาน)
        config_model = self.env['commission.branch.config']
        total_ratio = config_model.get_total_ratio_for_branch(self.branch_id.id)
        my_ratio = config_model.get_ratio_for_employee(self.branch_id.id, self.employee_id.id)

        _logger.info("[COMMISSION BRANCH] จำนวนพนักงาน active ในสาขา '%s' = %d คน | สัดส่วนรวม = %.2f | สัดส่วนตัวเอง = %.2f",
                     emp_branch_name, len(active_employees), total_ratio, my_ratio)

        if total_ratio <= 0 or my_ratio <= 0:
            _logger.info("[COMMISSION BRANCH] สัดส่วนรวม=%.2f หรือ สัดส่วนตัวเอง=%.2f = 0 → ค่าคอม = 0", total_ratio, my_ratio)
            self.income_commission = 0.0
            return

        # รายชื่อ database ที่ต้องดึง
        db_list = ['NPD_Intertrading_New', 'NPD_S_Group_New_V2', 'NPD_Bangkok_New']
        login_url = 'https://npderp.com/web/session/authenticate'
        commission_url = 'https://npderp.com/api/commission/branch'
        login_user = 'Npd_admin'
        login_pass = '1234'

        total_net_rental = 0.0

        for db_name in db_list:
            try:
                # ===== Step 1: Login =====
                session = requests.Session()
                login_payload = {
                    "jsonrpc": "2.0",
                    "params": {
                        "db": db_name,
                        "login": login_user,
                        "password": login_pass
                    }
                }
                login_resp = session.post(login_url, json=login_payload, timeout=30)
                login_data = login_resp.json()

                if login_data.get('error'):
                    _logger.warning("[COMMISSION BRANCH] Login FAILED db=%s | error=%s", db_name, login_data['error'])
                    continue

                _logger.info("[COMMISSION BRANCH] Login OK db=%s", db_name)

                # ===== Step 2: ดึงข้อมูลค่าคอมสาขา =====
                commission_payload = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "month": month,
                        "year": int(year)
                    }
                }
                comm_resp = session.post(commission_url, json=commission_payload, timeout=60)
                comm_data = comm_resp.json()

                result = comm_data.get('result', {})
                if result.get('status') != 'success':
                    _logger.warning("[COMMISSION BRANCH] API FAILED db=%s | result=%s", db_name, result)
                    continue

                data_list = result.get('data', [])
                _logger.info("[COMMISSION BRANCH] db=%s | จำนวนข้อมูลทั้งหมด: %d", db_name, len(data_list))

                # ===== Log รายชื่อทั้งหมดจาก API =====
                for idx, item in enumerate(data_list):
                    _logger.info(
                        "[COMMISSION BRANCH] db=%s | [%d] branch_name='%s' | net_rental=%.2f",
                        db_name, idx,
                        item.get('branch_name', ''),
                        item.get('net_rental', 0.0)
                    )

                # ===== Step 3: กรองจากชื่อสาขา =====
                db_net_rental = 0.0
                found = False
                for item in data_list:
                    api_branch_name = (item.get('branch_name') or '').strip()

                    if api_branch_name == emp_branch_name:
                        net_rental = item.get('net_rental', 0.0)
                        db_net_rental += net_rental
                        found = True
                        _logger.info(
                            "[COMMISSION BRANCH] MATCH! db=%s | branch=%s | net_rental=%.2f",
                            db_name, api_branch_name, net_rental
                        )

                if not found:
                    _logger.info("[COMMISSION BRANCH] ไม่พบสาขาที่ตรงกัน db=%s | ค้นหา: %s",
                                 db_name, emp_branch_name)

                _logger.info("[COMMISSION BRANCH] ★ db=%s | net_rental รวม = %.2f", db_name, db_net_rental)
                total_net_rental += db_net_rental

            except Exception as e:
                _logger.exception("[COMMISSION BRANCH] ERROR db=%s | %s", db_name, str(e))
                continue

        _logger.info("[COMMISSION BRANCH] ★ net_rental สาขา รวมทั้ง 3 db = %.2f", total_net_rental)

        # ===== ดึงยอด Sales จาก API กรองตามสาขา + เดือน/ปี =====
        sales_commission_url = 'https://npderp.com/api/commission/sales'
        sales_total_net_rental = 0.0

        for db_name in db_list:
            try:
                session = requests.Session()
                login_payload = {
                    "jsonrpc": "2.0",
                    "params": {"db": db_name, "login": login_user, "password": login_pass}
                }
                login_resp = session.post(login_url, json=login_payload, timeout=30)
                login_data = login_resp.json()

                if login_data.get('error'):
                    continue

                commission_payload = {
                    "jsonrpc": "2.0", "method": "call",
                    "params": {"month": month, "year": int(year)}
                }
                sales_resp = session.post(sales_commission_url, json=commission_payload, timeout=60)
                sales_data = sales_resp.json()

                if sales_data.get('error'):
                    continue

                result_sales = sales_data.get('result', {})
                if result_sales.get('status') != 'success':
                    continue

                for item in result_sales.get('data', []):
                    api_branch = (item.get('branch_name') or '').strip()
                    if api_branch == emp_branch_name:
                        sales_total_net_rental += item.get('net_rental', 0.0)

            except Exception as e:
                _logger.exception("[COMMISSION BRANCH - SALES] ERROR db=%s | %s", db_name, str(e))
                continue

        _logger.info("[COMMISSION BRANCH] ★ net_rental Sales (สาขา %s) รวมทั้ง 3 db = %.2f",
                     emp_branch_name, sales_total_net_rental)

        # ===== ดึงยอด bankheaw จาก API (เฉพาะ NPD_S_Group_New_V2) =====
        bankheaw_url = 'https://npderp.com/api/commission/bankheaw'
        bankheaw_db = 'NPD_S_Group_New_V2'
        bankheaw_branch_net = 0.0
        bankheaw_sales_net = 0.0

        try:
            session = requests.Session()
            login_payload = {
                "jsonrpc": "2.0",
                "params": {"db": bankheaw_db, "login": login_user, "password": login_pass}
            }
            login_resp = session.post(login_url, json=login_payload, timeout=30)
            login_data = login_resp.json()

            if not login_data.get('error'):
                bk_payload = {
                    "jsonrpc": "2.0", "method": "call",
                    "params": {"month": month, "year": int(year)}
                }
                bk_resp = session.post(bankheaw_url, json=bk_payload, timeout=60)
                bk_data = bk_resp.json()

                result_bk = bk_data.get('result', {})
                if result_bk.get('status') == 'success':
                    for item in result_bk.get('data', []):
                        if item.get('sort_order', 0) != 0:
                            continue
                        api_branch = (item.get('branch_name') or '').strip()
                        if api_branch == emp_branch_name:
                            item_type = (item.get('type') or '').strip()
                            net = item.get('net_total', 0.0)
                            if item_type == 'สาขา':
                                bankheaw_branch_net += net
                            elif item_type == 'เซลล์':
                                bankheaw_sales_net += net

        except Exception as e:
            _logger.exception("[COMMISSION BRANCH - BANKHEAW] ERROR | %s", str(e))

        _logger.info("[COMMISSION BRANCH] ★ bankheaw สาขา = %.2f | bankheaw เซลล์ = %.2f",
                     bankheaw_branch_net, bankheaw_sales_net)

        total_net_rental += bankheaw_branch_net
        sales_total_net_rental += bankheaw_sales_net

        _logger.info("[COMMISSION BRANCH] ★ net_rental สาขา (รวม bankheaw) = %.2f", total_net_rental)
        _logger.info("[COMMISSION BRANCH] ★ net_rental Sales (รวม bankheaw) = %.2f", sales_total_net_rental)

        # ===== ดึงอัตราค่าคอมจากตั้งค่า =====
        rate_model = self.env['commission.rate.branch.sales']
        branch_rate, sales_rate = rate_model.get_rates()

        # ===== คำนวณ: คิดอัตราก่อนรวม =====
        branch_after_rate = total_net_rental * (branch_rate / 100.0)
        sales_after_rate = sales_total_net_rental * (sales_rate / 100.0)
        grand_total_net_rental = branch_after_rate + sales_after_rate
        commission_per_person = (grand_total_net_rental * my_ratio) / total_ratio

        _logger.info("=" * 60)
        _logger.info("[COMMISSION BRANCH] ★★★ net_rental สาขา = %.2f × %.2f%% = %.2f",
                     total_net_rental, branch_rate, branch_after_rate)
        _logger.info("[COMMISSION BRANCH] ★★★ net_rental Sales = %.2f × %.2f%% = %.2f",
                     sales_total_net_rental, sales_rate, sales_after_rate)
        _logger.info("[COMMISSION BRANCH] ★★★ grand_total (หลังคิดอัตรา) = %.2f", grand_total_net_rental)
        _logger.info("[COMMISSION BRANCH] ★★★ สัดส่วนตัวเอง = %.2f | สัดส่วนรวม = %.2f", my_ratio, total_ratio)
        _logger.info("[COMMISSION BRANCH] ★★★ ค่าคอมสาขา = %.2f × %.2f / %.2f = %.2f",
                     grand_total_net_rental, my_ratio, total_ratio, commission_per_person)
        _logger.info("=" * 60)

        # เซ็ตค่าลง field ค่าคอมมิชชั่นสาขา
        self.income_commission = commission_per_person

    def action_view_commission_branch_detail(self):
        """ปุ่มดูรายละเอียดค่าคอมมิชชั่นสาขา — แสดง popup ยอดแต่ละ DB"""
        self.ensure_one()

        emp_branch_name = (self.branch_id.name or '').strip()
        month = self.month
        year = str(self.year).strip()
        emp_fullname = ((self.firstname or '') + ' ' + (self.lastname or '')).strip()

        # คำนวณสัดส่วนจากตารางตั้งค่าคอมมิชชั่นสาขา (รายพนักงาน)
        config_model = self.env['commission.branch.config']
        my_ratio = 0.0
        total_ratio = 0.0
        active_emp_count = 0
        if self.branch_id:
            active_employees = self.env['employee.salary'].search([
                ('branch_id', '=', self.branch_id.id),
                ('status', '=', 'active'),
            ])
            active_emp_count = len(active_employees)
            total_ratio = config_model.get_total_ratio_for_branch(self.branch_id.id)
            my_ratio = config_model.get_ratio_for_employee(self.branch_id.id, self.employee_id.id)

        db_list = ['NPD_Intertrading_New', 'NPD_S_Group_New_V2', 'NPD_Bangkok_New']
        login_url = 'https://npderp.com/web/session/authenticate'
        commission_url = 'https://npderp.com/api/commission/branch'
        login_user = 'Npd_admin'
        login_pass = '1234'

        lines = []
        total_net_rental = 0.0

        for db_name in db_list:
            line_vals = {'db_name': db_name, 'status': '', 'match_count': 0, 'net_rental': 0.0}
            try:
                session = requests.Session()
                login_payload = {
                    "jsonrpc": "2.0",
                    "params": {"db": db_name, "login": login_user, "password": login_pass}
                }
                login_resp = session.post(login_url, json=login_payload, timeout=30)
                login_data = login_resp.json()

                if login_data.get('error'):
                    line_vals['status'] = 'Login Failed'
                    lines.append((0, 0, line_vals))
                    continue

                commission_payload = {
                    "jsonrpc": "2.0", "method": "call",
                    "params": {"month": month, "year": int(year)}
                }
                comm_resp = session.post(commission_url, json=commission_payload, timeout=60)
                comm_data = comm_resp.json()

                # ดัก error จาก Odoo (เช่น permission error)
                if comm_data.get('error'):
                    err_msg = comm_data['error'].get('data', {}).get('message', '') or comm_data['error'].get('message', '')
                    if 'not allowed' in err_msg or 'Access' in err_msg:
                        line_vals['status'] = 'ไม่พบข้อมูล / ไม่มีสิทธิ์เข้าถึง'
                    else:
                        line_vals['status'] = 'Error: %s' % err_msg[:60]
                    lines.append((0, 0, line_vals))
                    continue

                result = comm_data.get('result', {})

                if result.get('status') != 'success':
                    line_vals['status'] = 'ไม่สามารถดึงข้อมูลได้'
                    lines.append((0, 0, line_vals))
                    continue

                data_list = result.get('data', [])
                db_net_rental = 0.0
                match_count = 0
                for item in data_list:
                    api_branch = (item.get('branch_name') or '').strip()
                    if api_branch == emp_branch_name:
                        db_net_rental += item.get('net_rental', 0.0)
                        match_count += 1

                line_vals['net_rental'] = db_net_rental
                line_vals['match_count'] = match_count
                line_vals['status'] = 'สำเร็จ' if match_count > 0 else 'ไม่พบข้อมูลที่ตรงกัน'
                total_net_rental += db_net_rental

            except Exception as e:
                line_vals['status'] = 'Error: %s' % str(e)[:80]

            lines.append((0, 0, line_vals))

        # ===== ดึงยอด Sales จาก API กรองตามสาขา + เดือน/ปี =====
        sales_commission_url = 'https://npderp.com/api/commission/sales'
        sales_lines = []
        sales_total_net_rental = 0.0

        for db_name in db_list:
            try:
                session = requests.Session()
                login_payload = {
                    "jsonrpc": "2.0",
                    "params": {"db": db_name, "login": login_user, "password": login_pass}
                }
                login_resp = session.post(login_url, json=login_payload, timeout=30)
                login_data = login_resp.json()

                if login_data.get('error'):
                    continue

                commission_payload = {
                    "jsonrpc": "2.0", "method": "call",
                    "params": {"month": month, "year": int(year)}
                }
                sales_resp = session.post(sales_commission_url, json=commission_payload, timeout=60)
                sales_data = sales_resp.json()

                if sales_data.get('error'):
                    continue

                result_sales = sales_data.get('result', {})
                if result_sales.get('status') != 'success':
                    continue

                data_list_sales = result_sales.get('data', [])

                # กรองเฉพาะสาขาเดียวกัน
                for item in data_list_sales:
                    api_branch = (item.get('branch_name') or '').strip()
                    if api_branch == emp_branch_name:
                        net_rental_sales = item.get('net_rental', 0.0)
                        sales_total_net_rental += net_rental_sales
                        sales_lines.append((0, 0, {
                            'db_name': db_name,
                            'sales_contact_name': item.get('sales_contact_name', ''),
                            'branch_name': api_branch,
                            'rental_amount': item.get('rental_amount', 0.0),
                            'payment_received': item.get('payment_received', 0.0),
                            'outstanding_debt': item.get('outstanding_debt', 0.0),
                            'shipping_cost': item.get('shipping_cost', 0.0),
                            'net_rental': net_rental_sales,
                        }))

            except Exception as e:
                _logger.exception("[COMMISSION BRANCH DETAIL - SALES] ERROR db=%s | %s", db_name, str(e))
                continue

        # ===== ดึงยอด bankheaw จาก API (เฉพาะ NPD_S_Group_New_V2) =====
        bankheaw_url = 'https://npderp.com/api/commission/bankheaw'
        bankheaw_db = 'NPD_S_Group_New_V2'

        try:
            session = requests.Session()
            login_payload = {
                "jsonrpc": "2.0",
                "params": {"db": bankheaw_db, "login": login_user, "password": login_pass}
            }
            login_resp = session.post(login_url, json=login_payload, timeout=30)
            login_data = login_resp.json()

            if not login_data.get('error'):
                bk_payload = {
                    "jsonrpc": "2.0", "method": "call",
                    "params": {"month": month, "year": int(year)}
                }
                bk_resp = session.post(bankheaw_url, json=bk_payload, timeout=60)
                bk_data = bk_resp.json()

                result_bk = bk_data.get('result', {})
                if result_bk.get('status') == 'success':
                    for item in result_bk.get('data', []):
                        if item.get('sort_order', 0) != 0:
                            continue
                        api_branch = (item.get('branch_name') or '').strip()
                        if api_branch == emp_branch_name:
                            item_type = (item.get('type') or '').strip()
                            net = item.get('net_total', 0.0)

                            if item_type == 'สาขา':
                                # type=สาขา → เพิ่มใน detail_line_ids (ยอดสาขา)
                                lines.append((0, 0, {
                                    'db_name': bankheaw_db + ' (bankheaw)',
                                    'status': 'สำเร็จ',
                                    'match_count': 1,
                                    'net_rental': net,
                                }))
                                total_net_rental += net

                            elif item_type == 'เซลล์':
                                # type=เซลล์ → เพิ่มใน sales_line_ids (ยอด Sales)
                                sales_lines.append((0, 0, {
                                    'db_name': bankheaw_db + ' (bankheaw)',
                                    'sales_contact_name': item.get('salesperson_name', ''),
                                    'branch_name': api_branch,
                                    'rental_amount': item.get('total_rent_revenue', 0.0),
                                    'payment_received': item.get('total_paid', 0.0),
                                    'outstanding_debt': item.get('net_outstanding', 0.0),
                                    'shipping_cost': 0.0,
                                    'net_rental': net,
                                }))
                                sales_total_net_rental += net

        except Exception as e:
            _logger.exception("[COMMISSION BRANCH DETAIL - BANKHEAW] ERROR | %s", str(e))

        # ===== ดึงอัตราค่าคอมจากตั้งค่า =====
        rate_model = self.env['commission.rate.branch.sales']
        branch_rate, sales_rate = rate_model.get_rates()

        # ===== คำนวณ: คิดอัตราก่อนรวม =====
        branch_after_rate = total_net_rental * (branch_rate / 100.0)
        sales_after_rate = sales_total_net_rental * (sales_rate / 100.0)
        grand_total = branch_after_rate + sales_after_rate
        per_person = (grand_total * my_ratio / total_ratio) if total_ratio > 0 and my_ratio > 0 else 0.0

        wizard = self.env['commission.detail.wizard'].create({
            'commission_type': 'branch',
            'employee_name': emp_fullname,
            'branch_name': emp_branch_name,
            'month': month,
            'year': year,
            'detail_line_ids': lines,
            'sales_line_ids': sales_lines,
            'sales_total_net_rental': sales_total_net_rental,
            'grand_total_net_rental': grand_total,
            'total_amount': total_net_rental,
            'branch_comm_rate': branch_rate,
            'sales_comm_rate': sales_rate,
            'branch_after_rate': branch_after_rate,
            'sales_after_rate': sales_after_rate,
            'active_emp_count': active_emp_count,
            'per_person_amount': per_person,
            'my_ratio': my_ratio,
            'total_ratio': total_ratio,
        })

        return {
            'name': 'รายละเอียดค่าคอมมิชชั่นสาขา',
            'type': 'ir.actions.act_window',
            'res_model': 'commission.detail.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_commission_sale_detail(self):
        """ปุ่มดูรายละเอียดค่าคอมมิชชั่น Sales — แสดง popup ยอดแต่ละ DB"""
        self.ensure_one()

        emp_firstname = (self.firstname or '').strip()
        emp_lastname = (self.lastname or '').strip()
        emp_fullname = (emp_firstname + ' ' + emp_lastname).strip()
        emp_branch_name = (self.branch_id.name or '').strip()
        month = self.month
        year = str(self.year).strip()

        db_list = ['NPD_Intertrading_New', 'NPD_S_Group_New_V2', 'NPD_Bangkok_New']
        login_url = 'https://npderp.com/web/session/authenticate'
        commission_url = 'https://npderp.com/api/commission/sales'
        login_user = 'Npd_admin'
        login_pass = '1234'

        lines = []
        total_commission = 0.0

        for db_name in db_list:
            line_vals = {'db_name': db_name, 'status': '', 'match_count': 0, 'net_rental': 0.0}
            try:
                session = requests.Session()
                login_payload = {
                    "jsonrpc": "2.0",
                    "params": {"db": db_name, "login": login_user, "password": login_pass}
                }
                login_resp = session.post(login_url, json=login_payload, timeout=30)
                login_data = login_resp.json()

                if login_data.get('error'):
                    line_vals['status'] = 'Login Failed'
                    lines.append((0, 0, line_vals))
                    continue

                commission_payload = {
                    "jsonrpc": "2.0", "method": "call",
                    "params": {"month": month, "year": int(year)}
                }
                comm_resp = session.post(commission_url, json=commission_payload, timeout=60)
                comm_data = comm_resp.json()

                # ดัก error จาก Odoo (เช่น permission error)
                if comm_data.get('error'):
                    err_msg = comm_data['error'].get('data', {}).get('message', '') or comm_data['error'].get('message', '')
                    if 'not allowed' in err_msg or 'Access' in err_msg:
                        line_vals['status'] = 'ไม่พบข้อมูล / ไม่มีสิทธิ์เข้าถึง'
                    else:
                        line_vals['status'] = 'Error: %s' % err_msg[:60]
                    lines.append((0, 0, line_vals))
                    continue

                result = comm_data.get('result', {})

                if result.get('status') != 'success':
                    line_vals['status'] = 'ไม่สามารถดึงข้อมูลได้'
                    lines.append((0, 0, line_vals))
                    continue

                data_list = result.get('data', [])
                db_net_rental = 0.0
                match_count = 0
                for item in data_list:
                    api_sales_name = (item.get('sales_contact_name') or '').strip()
                    if api_sales_name == emp_fullname:
                        db_net_rental += item.get('net_rental', 0.0)
                        match_count += 1

                line_vals['net_rental'] = db_net_rental
                line_vals['match_count'] = match_count
                line_vals['status'] = 'สำเร็จ' if match_count > 0 else 'ไม่พบข้อมูลที่ตรงกัน'
                total_commission += db_net_rental

            except Exception as e:
                line_vals['status'] = 'Error: %s' % str(e)[:80]

            lines.append((0, 0, line_vals))

        # ===== ดึงยอด bankheaw (เฉพาะ NPD_S_Group_New_V2, type=เซลล์, กรองชื่อ) =====
        bankheaw_url = 'https://npderp.com/api/commission/bankheaw'
        bankheaw_db = 'NPD_S_Group_New_V2'
        bk_line_vals = {'db_name': bankheaw_db + ' (bankheaw)', 'status': '', 'match_count': 0, 'net_rental': 0.0}

        try:
            session = requests.Session()
            login_payload = {
                "jsonrpc": "2.0",
                "params": {"db": bankheaw_db, "login": login_user, "password": login_pass}
            }
            login_resp = session.post(login_url, json=login_payload, timeout=30)
            login_data = login_resp.json()

            if login_data.get('error'):
                bk_line_vals['status'] = 'Login Failed'
            else:
                bk_payload = {
                    "jsonrpc": "2.0", "method": "call",
                    "params": {"month": month, "year": int(year)}
                }
                bk_resp = session.post(bankheaw_url, json=bk_payload, timeout=60)
                bk_data = bk_resp.json()

                if bk_data.get('error'):
                    err_msg = bk_data['error'].get('data', {}).get('message', '') or bk_data['error'].get('message', '')
                    bk_line_vals['status'] = 'Error: %s' % err_msg[:60]
                else:
                    result_bk = bk_data.get('result', {})
                    if result_bk.get('status') == 'success':
                        bk_net = 0.0
                        bk_count = 0
                        for item in result_bk.get('data', []):
                            if item.get('sort_order', 0) != 0:
                                continue
                            item_type = (item.get('type') or '').strip()
                            if item_type != 'เซลล์':
                                continue
                            api_sales_name = (item.get('salesperson_name') or '').strip()
                            if emp_fullname and emp_fullname in api_sales_name:
                                bk_net += item.get('net_total', 0.0)
                                bk_count += 1

                        bk_line_vals['net_rental'] = bk_net
                        bk_line_vals['match_count'] = bk_count
                        bk_line_vals['status'] = 'สำเร็จ' if bk_count > 0 else 'ไม่พบข้อมูลที่ตรงกัน'
                        total_commission += bk_net
                    else:
                        bk_line_vals['status'] = 'ไม่สามารถดึงข้อมูลได้'

        except Exception as e:
            bk_line_vals['status'] = 'Error: %s' % str(e)[:80]

        lines.append((0, 0, bk_line_vals))

        wizard = self.env['commission.detail.wizard'].create({
            'commission_type': 'sale',
            'employee_name': emp_fullname,
            'branch_name': emp_branch_name,
            'month': month,
            'year': year,
            'detail_line_ids': lines,
            'total_amount': total_commission,
            'active_emp_count': 0,
            'per_person_amount': 0.0,
            'commission_rate': self._get_sales_commission_rate(total_commission),
            'commission_result': total_commission * (self._get_sales_commission_rate(total_commission) / 100.0),
        })

        return {
            'name': 'รายละเอียดค่าคอมมิชชั่น Sales',
            'type': 'ir.actions.act_window',
            'res_model': 'commission.detail.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def unlink(self):
        for record in self:
            data = {'odoo_id': record.id}
            self._send_data_to_php_api('delete', data)
        return super(PayrollSalary, self).unlink()

    @api.depends('year')
    def _compute_holiday_template(self):
        for rec in self:
            rec.holiday_template_year = rec.year

    def _prepare_ot_lines(self):
        self.ensure_one()
        if not self.ot_api_url or not self.employee_code:
            return [], 0, None

        params = {'employee_code': self.employee_code, 'month': self.month, 'year': self.year}
        _logger.info("OT API Request URL: %s", self.ot_api_url)
        _logger.info("OT API Payload (params): %s", json.dumps(params, indent=2, ensure_ascii=False))

        try:
            response = requests.get(self.ot_api_url, params=params, timeout=10)
            response.raise_for_status()
            ot_logs = response.json()
            _logger.info("OT API Response: %s", json.dumps(ot_logs, indent=2, ensure_ascii=False))
            if not ot_logs:
                return [], 0, None
        except requests.exceptions.MissingSchema:
            warning_dict = {
                'warning': {'title': _("API URL Error"),
                            'message': _("รูปแบบ API URL ไม่ถูกต้อง กรุณาขึ้นต้นด้วย http:// หรือ https://")}
            }
            return [], 0, warning_dict
        except requests.exceptions.RequestException as e:
            warning_dict = {
                'warning': {'title': _("API Connection Error"),
                            'message': _("ไม่สามารถเชื่อมต่อ API ได้: %s") % e}
            }
            return [], 0, warning_dict

        # -----------------------------
        # ✅ ดึงตารางกะทำงานของพนักงาน
        work_schedule = self.env['hr.work.schedule'].search([('employee_id', '=', self.employee_id.id)], limit=1)

        # ✅ ดึงวันหยุดนักขัตฤกษ์ของปี
        holiday_template = self.env['payroll.holiday'].search([('year', '=', self.year)], limit=1)
        holidays = [line.date.strftime('%Y-%m-%d') for line in holiday_template.line_ids] if holiday_template else []

        # 👉 ต้องมีโค้ด generate OT line ที่นี่
        # เช่น:
        ot_lines_to_create = []
        total_ot_amount = 0.0

        # ✅ เงินเดือนต่อชั่วโมง (ฐานเงินเดือน / 30 วัน / 8 ชั่วโมง)
        # ✅ เงินเดือนต่อชั่วโมง (ปัดเศษ)
        salary_per_day = self.base_salary / 30
        hourly_rate_raw = salary_per_day / 8.0
        hourly_rate = round_half_up(hourly_rate_raw)

        for log in ot_logs:
            # ดึงวันที่จาก log['work_date']
            work_date = fields.Date.from_string(log['work_date'])

            # รวมวันที่กับเวลา
            start_str = f"{work_date} {log['start_time']}"
            end_str = f"{work_date} {log['end_time']}"

            start_time_x = log['start_time']
            end_time_x = log['end_time']

            start_dt = fields.Datetime.from_string(start_str)
            end_dt = fields.Datetime.from_string(end_str)

            if end_dt <= start_dt:
                end_dt += datetime.timedelta(days=1)

            # คำนวณชั่วโมง OT
            ot_hours = (end_dt - start_dt).total_seconds() / 3600.0

            if self.ot_calculation_method == 'round_down':
                if ot_hours < 1:
                    ot_hours = 0
                else:
                    # ชั่วโมงแรกคิดเต็ม (1 ชม.)
                    first_hour = 1
                    remaining_hours = ot_hours - 1
                    ot_hours = first_hour + max(0, remaining_hours)

            # ✅ ถ้าเป็นวันหยุดนักขัตฤกษ์
            if work_date.strftime('%Y-%m-%d') in holidays:
                ot_type = 'holiday'
                multiplier = 2.0
                ot_hours = (end_dt - start_dt).total_seconds() / 3600.0
            else:
                if self._is_outside_shift(work_date, start_dt, end_dt, work_schedule):
                    ot_type = 'weekday'
                    multiplier = 1.5

                    # ✅ ตัดเวลาที่อยู่ในกะออก
                    shift_start, shift_end = self._get_shift_time(work_date, work_schedule)
                    ot_hours = self._calculate_ot_outside_shift(start_dt, end_dt, shift_start, shift_end)
                else:
                    ot_type = 'sunday'
                    multiplier = 1.0

            ot_amount = ot_hours * hourly_rate * multiplier
            total_ot_amount += ot_amount

            ot_lines_to_create.append((0, 0, {
                'date': work_date,
                'start_time': start_dt,
                'end_time': end_dt,
                'start_time_x': start_time_x,
                'end_time_x': end_time_x,
                'ot_hours': ot_hours,
                'ot_amount': ot_amount,
                'ot_type': ot_type,
            }))

        return ot_lines_to_create, total_ot_amount, None

    def _get_shift_time(self, work_date, work_schedule):
        weekday_idx = work_date.weekday()
        shift_map = {
            0: (work_schedule.mon_shift_start, work_schedule.mon_shift_end),
            1: (work_schedule.tue_shift_start, work_schedule.tue_shift_end),
            2: (work_schedule.wed_shift_start, work_schedule.wed_shift_end),
            3: (work_schedule.thu_shift_start, work_schedule.thu_shift_end),
            4: (work_schedule.fri_shift_start, work_schedule.fri_shift_end),
            5: (work_schedule.sat_shift_start, work_schedule.sat_shift_end),
            6: (0, 0),  # อาทิตย์
        }
        start_hour, end_hour = shift_map.get(weekday_idx, (0, 0))
        shift_start_dt = datetime.datetime.combine(work_date,
                                                   datetime.time(int(start_hour), int((start_hour % 1) * 60)))
        shift_end_dt = datetime.datetime.combine(work_date, datetime.time(int(end_hour), int((end_hour % 1) * 60)))
        return shift_start_dt, shift_end_dt

    def _calculate_ot_outside_shift(self, start_dt, end_dt, shift_start_dt, shift_end_dt):
        """
        ตัดเวลาที่อยู่ในกะออก คงเหลือแค่ช่วงนอกกะ
        """
        ot_hours = 0.0

        # ก่อนกะ
        if start_dt < shift_start_dt:
            before_shift_end = min(end_dt, shift_start_dt)
            ot_hours += (before_shift_end - start_dt).total_seconds() / 3600.0

        # หลังเลิกกะ
        if end_dt > shift_end_dt:
            after_shift_start = max(start_dt, shift_end_dt)
            ot_hours += (end_dt - after_shift_start).total_seconds() / 3600.0

        # 🟢 ตัดเวลาพักกลางวันออก (12:00–13:00)
        lunch_start = datetime.datetime.combine(start_dt.date(), datetime.time(12, 0))
        lunch_end = datetime.datetime.combine(start_dt.date(), datetime.time(13, 0))

        overlap_start = max(start_dt, lunch_start)
        overlap_end = min(end_dt, lunch_end)

        if overlap_start < overlap_end:
            lunch_hours = (overlap_end - overlap_start).total_seconds() / 3600.0
            ot_hours -= lunch_hours

        return max(0, ot_hours)

    def _is_outside_shift(self, work_date, start_dt, end_dt, work_schedule):
        """เช็คว่าเวลา OT อยู่นอกช่วงกะงานหรือไม่"""
        weekday_idx = work_date.weekday()  # Monday=0 ... Sunday=6
        shift_map = {
            0: (work_schedule.work_mon, work_schedule.mon_shift_start, work_schedule.mon_shift_end),
            1: (work_schedule.work_tue, work_schedule.tue_shift_start, work_schedule.tue_shift_end),
            2: (work_schedule.work_wed, work_schedule.wed_shift_start, work_schedule.wed_shift_end),
            3: (work_schedule.work_thu, work_schedule.thu_shift_start, work_schedule.thu_shift_end),
            4: (work_schedule.work_fri, work_schedule.fri_shift_start, work_schedule.fri_shift_end),
            5: (work_schedule.work_sat, work_schedule.sat_shift_start, work_schedule.sat_shift_end),
            6: (False, 0, 0),  # อาทิตย์ = ไม่ทำงาน
        }
        is_workday, shift_start, shift_end = shift_map.get(weekday_idx, (False, 0, 0))

        if not is_workday:
            return True  # วันหยุดตามตาราง

        # แปลงเป็น datetime
        shift_start_dt = datetime.datetime.combine(
            work_date, datetime.time(int(shift_start), int((shift_start % 1) * 60))
        )
        shift_end_dt = datetime.datetime.combine(
            work_date, datetime.time(int(shift_end), int((shift_end % 1) * 60))
        )

        # ถ้า OT อยู่นอกช่วงเวลา
        return start_dt < shift_start_dt or end_dt > shift_end_dt

    def _prepare_lateness_data(self):
        self.ensure_one()
        if not self.lateness_api_url or not self.employee_id:
            # คืนค่า 10 ตัวให้ครบรูปแบบ
            return 0, 0, 0, 0, 0, 0, 0, 0, 0, None

        work_schedule = self.env['hr.work.schedule'].search([('employee_id', '=', self.employee_id.id)], limit=1)
        if not work_schedule:
            _logger.warning("ไม่พบข้อมูลตารางการทำงานสำหรับพนักงานนี้: %s", self.employee_id.firstname)
            return 0, 0, 0, 0, 0, 0, 0, 0, 0, {
                'warning': {
                    'title': _("ข้อมูลไม่ครบ"),
                    'message': _("ไม่พบข้อมูลตารางการทำงานสำหรับพนักงานนี้ กรุณาตั้งค่าในเมนู 'ตารางการทำงาน' ก่อน")
                }
            }

        schedule_data = {
            'work_mon': work_schedule.work_mon, 'mon_shift_start': work_schedule.mon_shift_start,
            'mon_shift_end': work_schedule.mon_shift_end,
            'work_tue': work_schedule.work_tue, 'tue_shift_start': work_schedule.tue_shift_start,
            'tue_shift_end': work_schedule.tue_shift_end,
            'work_wed': work_schedule.work_wed, 'wed_shift_start': work_schedule.wed_shift_start,
            'wed_shift_end': work_schedule.wed_shift_end,
            'work_thu': work_schedule.work_thu, 'thu_shift_start': work_schedule.thu_shift_start,
            'thu_shift_end': work_schedule.thu_shift_end,
            'work_fri': work_schedule.work_fri, 'fri_shift_start': work_schedule.fri_shift_start,
            'fri_shift_end': work_schedule.fri_shift_end,
            'work_sat': work_schedule.work_sat, 'sat_shift_start': work_schedule.sat_shift_start,
            'sat_shift_end': work_schedule.sat_shift_end,
        }

        current_year_holiday_template = self.env['payroll.holiday'].search([('year', '=', self.year)], limit=1)
        official_holidays = [line.date.strftime('%Y-%m-%d') for line in
                             current_year_holiday_template.line_ids] if current_year_holiday_template else []

        payload = {
            'employee_code': self.employee_id.employee_code,
            'grace_period': self.lateness_grace_period,
            'work_schedule': schedule_data,
            'month': self.month,
            'year': self.year,
            'cutoff_day': self.cutoff_day,
            'official_holidays': official_holidays,
        }

        _logger.info("Lateness API Payload: %s", json.dumps(payload, indent=2, ensure_ascii=False))
        try:
            response = requests.post(self.lateness_api_url, json=payload, timeout=10)
            response.raise_for_status()
            api_response = response.json()
            _logger.info("Lateness API Response: %s", json.dumps(api_response, indent=2, ensure_ascii=False))

            if api_response.get('status') == 'success':
                return (
                    api_response.get('total_late_checkin_minutes', 0),  # 1
                    api_response.get('total_early_checkout_minutes', 0),  # 2
                    api_response.get('missed_days', 0),  # 3
                    api_response.get('total_lateness_minutes', 0),  # 4
                    api_response.get('working_days_count', 0),  # 5
                    api_response.get('leave_deduction_total', 0),  # 6
                    api_response.get('deduction_absent', 0),  # 7  (ขาดงานเต็มวันอย่างเดียว)
                    api_response.get('early_checkout_deduction', 0),  # 8  (ออกก่อนเวลา แปลงเป็นนาที→เงิน)
                    api_response.get('deduction_absent_total', 0),  # 9  (รวม ขาดงาน + ออกก่อนเวลา)
                    None  # 10 warning
                )
            else:
                warning_dict = {
                    'warning': {'title': _("API Error"), 'message': api_response.get('message', "Unknown error")}
                }
                return 0, 0, 0, 0, 0, 0, 0, 0, 0, warning_dict

        except requests.exceptions.RequestException as e:
            warning_dict = {
                'warning': {'title': _("API Connection Error"), 'message': _("ไม่สามารถเชื่อมต่อ API ได้: %s") % e}
            }
            return 0, 0, 0, 0, 0, 0, 0, 0, 0, warning_dict

    def _populate_all_lines(self):
        self.ensure_one()
        ot_lines_commands, total_ot_amount, ot_warning_dict = self._prepare_ot_lines()
        (late_checkin_minutes,
         early_checkout_minutes,
         missed_days,
         total_lateness_minutes,
         working_days_count,
         leave_deduction_total,
         deduction_absent,  # ขาดงานเต็มวัน
         early_checkout_deduction,  # ออกก่อนเวลา คิดเป็นเงินต่อนาที
         deduction_absent_total,  # รวมสองอันบนแล้ว
         lateness_warning_dict) = self._prepare_lateness_data()

        if not self.manual_override:
            # set lateness values
            self.late_checkin_minutes = late_checkin_minutes
            self.early_checkout_minutes = early_checkout_minutes
            self.missed_days = missed_days
            self.lateness_minutes = total_lateness_minutes
            self.leave_deduction_total = round_half_up(leave_deduction_total)


            # ✅ เก็บค่าแยกไว้เพื่อแสดง/ส่งต่อ (ปัดเศษด้วย round_half_up)
            self.early_checkout_deduction = round_half_up(early_checkout_deduction)

            # ✅ ใช้ “รวม” เป็นยอดหักขาดงาน (รวมออกก่อนเวลาแล้ว)
            self.deduction_absent = round_half_up(deduction_absent_total)
            self.missed_days_deduction = round_half_up(deduction_absent_total)

            # -----------------------------
            # คำนวณเงินหัก "สาย" ตามสูตรเดิมเท่านั้น
            # -----------------------------
            salary_per_day = self.base_salary / 30.0

            total_work_hours = 0.0
            work_days_count = 0
            work_schedule = self.env['hr.work.schedule'].search([('employee_id', '=', self.employee_id.id)], limit=1)
            if work_schedule:
                day_mapping = [
                    (work_schedule.work_mon, work_schedule.mon_shift_start, work_schedule.mon_shift_end),
                    (work_schedule.work_tue, work_schedule.tue_shift_start, work_schedule.tue_shift_end),
                    (work_schedule.work_wed, work_schedule.wed_shift_start, work_schedule.wed_shift_end),
                    (work_schedule.work_thu, work_schedule.thu_shift_start, work_schedule.thu_shift_end),
                    (work_schedule.work_fri, work_schedule.fri_shift_start, work_schedule.fri_shift_end),
                    (work_schedule.work_sat, work_schedule.sat_shift_start, work_schedule.sat_shift_end),
                ]
                for is_work, start, end in day_mapping:
                    if is_work and end > start:
                        work_hours = end - start
                        if work_hours >= 9:
                            work_hours -= 1
                        total_work_hours += work_hours
                        work_days_count += 1

            average_daily_hours = (total_work_hours / work_days_count) if work_days_count > 0 else 8.0
            hourly_rate = salary_per_day / average_daily_hours if average_daily_hours > 0 else 0.0
            salary_per_minute = hourly_rate / 60.0

            late_raw = self.late_checkin_minutes * salary_per_minute
            self.late_checkin_deduction = round_half_up(late_raw)

            self.deduction_late = self.late_checkin_deduction
            self.deduction_leave = round_half_up(self.leave_deduction_total)

            # ✅ ห้ามบวก early_checkout_deduction ซ้ำอีก เพราะรวมอยู่ใน deduction_absent แล้ว
            self.lateness_deduction = (
                    self.deduction_late +
                    self.deduction_leave +
                    self.deduction_absent
            )

            _logger.info(
                "[LATE-DEDUCTION] Emp=%s | Base=%.2f | PerDay=%.2f | AvgHours=%.2f | PerHour=%.2f | PerMinute=%.4f | "
                "LateMinutes=%s | LateRaw=%.4f -> LateDeduct(rounded)=%.2f | "
                "EarlyMinutes=%s | EarlyAsAbsent(THB)=%.2f | "
                "AbsentDays(THB without early)=%.2f | AbsentTotal(THB with early)=%.2f",
                self.employee_code,
                self.base_salary,
                salary_per_day,
                average_daily_hours,
                hourly_rate,
                salary_per_minute,
                self.late_checkin_minutes, late_raw, self.late_checkin_deduction,
                self.early_checkout_minutes, self.early_checkout_deduction,
                deduction_absent, deduction_absent_total
            )

        # -------------------
        # 🟢 สร้าง line รายละเอียดเงินเดือน
        # -------------------
        lines_to_create = []

        # ฐานเงินเดือน
        lines_to_create.append((0, 0, {
            'name': 'เงินเดือน',
            'type': 'income',
            'amount': self.base_salary
        }))

        # OT รวม
        lines_to_create.append((0, 0, {
                'name': 'ค่าล่วงเวลา/โอที',
                'type': 'income',
                'amount': self.manual_ot_weekday if self.override_ot else self.ot_total_weekday
            }))


        lines_to_create.append((0, 0, {
                'name': 'ค่าล่วงเวลา/วันหยุดนักขัตฤกษ์',
                'type': 'income',
                'amount': self.manual_ot_holiday if self.override_ot else self.ot_total_holiday
            }))


        lines_to_create.append((0, 0, {
                'name': 'ค่าล่วงเวลา',
                'type': 'income',
                'amount': self.manual_ot_sunday if self.override_ot else self.ot_total_sunday
            }))

        # รายได้เสริมจาก employee.salary

        lines_to_create.append(
                (0, 0, {'name': 'เงินค่าครองชีพ', 'type': 'income', 'amount': self.income_cost_of_living}))

        lines_to_create.append(
                (0, 0, {'name': 'เงินประจำตำแหน่ง', 'type': 'income', 'amount': self.income_position_allowance}))

        lines_to_create.append(
                (0, 0, {'name': 'เงินค่าประสบการณ์', 'type': 'income', 'amount': self.income_experience_allowance}))

        lines_to_create.append(
                (0, 0, {'name': 'เงินค่าวิชาชีพ', 'type': 'income', 'amount': self.income_professional_allowance}))

        # รายได้ใหม่

        lines_to_create.append((0, 0, {'name': 'เบี้ยเลี้ยง', 'type': 'income', 'amount': self.income_allowance}))

        lines_to_create.append((0, 0, {'name': 'ค่าอาหาร', 'type': 'income', 'amount': self.income_food}))

        lines_to_create.append((0, 0, {'name': 'ค่าเดินทาง', 'type': 'income', 'amount': self.income_transport}))

        lines_to_create.append((0, 0, {'name': 'อินเซนทีฟ', 'type': 'income', 'amount': self.income_fuel}))

        lines_to_create.append(
                (0, 0, {'name': 'ค่าคอมมิชชั่น', 'type': 'income', 'amount': self.income_commission + self.income_commission_sale}))

        # รายได้อื่นๆ (ฟิลด์ income_other มี auto-bump ให้ >= other_income_total แล้ว)
        lines_to_create.append((0, 0, {
            'name': 'รายได้อื่นๆ',
            'type': 'income',
            'amount': self.income_other
        }))

        # รายจ่ายใหม่

        lines_to_create.append(
                (0, 0, {'name': 'กองทุนสำรองเลี้ยงชีพ', 'type': 'deduction', 'amount': self.expense_provident}))

        lines_to_create.append(
                (0, 0, {'name': 'เบิกเงินล่วงหน้า', 'type': 'deduction', 'amount': self.expense_advance}))

        lines_to_create.append((0, 0, {'name': 'เงินกู้', 'type': 'deduction', 'amount': self.expense_loan}))

        lines_to_create.append((0, 0, {'name': 'กยศ', 'type': 'deduction', 'amount': self.expense_ksl}))

        lines_to_create.append(
                (0, 0, {'name': 'เงินประกันการทำงาน', 'type': 'deduction', 'amount': self.expense_insurance}))

        lines_to_create.append(
            (0, 0, {'name': 'หักเงินอื่นๆ', 'type': 'deduction', 'amount': self.expense_other}))

        # หักสาย / ลา / ขาดงาน

        lines_to_create.append((0, 0, {'name': 'หักสาย', 'type': 'deduction', 'amount': self.deduction_late}))

        lines_to_create.append((0, 0, {'name': 'หักลากิจ', 'type': 'deduction', 'amount': self.deduction_leave}))

        lines_to_create.append((0, 0, {
            'name': 'หักขาดงาน',
            'type': 'deduction',
            'amount': self.missed_days_deduction
        }))

        # ประกันสังคม
        sso_base = max(self.sso_min_wage, min(self.base_salary, self.sso_max_wage))
        sso_amount = sso_base * (self.sso_rate / 100.0)
        lines_to_create.append((0, 0, {
            'name': 'ประกันสังคม',
            'type': 'deduction',
            'amount': sso_amount
        }))

        # กองทุนสำรองเลี้ยงชีพ (rate-based)
        if self.provident_fund_rate > 0:
            provident_fund_amount = self.base_salary * (self.provident_fund_rate / 100.0)
            lines_to_create.append((0, 0, {
                'name': 'กองทุนสำรองเลี้ยงชีพ',
                'type': 'deduction',
                'amount': provident_fund_amount
            }))

        # ภาษี
        temp_gross_income = self.base_salary + total_ot_amount
        temp_tax, _ = self._calculate_tax(temp_gross_income, sso_amount)
        # ภาษีหัก ณ ที่จ่าย
        tax_line = self.line_ids.filtered(lambda l: l.name == 'ภาษีหัก ณ ที่จ่าย')
        if tax_line:
            tax_amount = tax_line.amount if tax_line.amount > 0 else self.tax_monthly
        else:
            tax_amount = self.tax_monthly

        lines_to_create.append((0, 0, {
            'name': 'ภาษีหัก ณ ที่จ่าย',
            'type': 'deduction',
            'amount': tax_amount
        }))

        # Apply to record
        # ถ้า override_ot=True → เก็บ ot_line_ids เดิมที่ user แก้ไว้ (ไม่ regenerate)
        if not self.override_ot:
            self.ot_line_ids = [(5, 0, 0)] + ot_lines_commands
        else:
            _logger.info("[OVERRIDE OT] Skip auto-update ot_line_ids for payroll %s", self.id)

        if not self.manual_override:
            self.line_ids = [(5, 0, 0)] + lines_to_create
        else:
            _logger.info("[MANUAL OVERRIDE] Skip auto-update line_ids for payroll %s", self.id)

        final_warning = ot_warning_dict or lateness_warning_dict
        return final_warning

    @api.onchange('employee_id', 'ot_calculation_method', 'month', 'year')
    def _onchange_employee_id(self):
        if self.employee_id and self.month and self.year:
            self._fetch_vehicle_booking_data()
            self._fetch_commission_branch_data()
            self._fetch_commission_sales_data()
            warning_dict = self._populate_all_lines()
            if warning_dict:
                return warning_dict
        else:
            if not self.manual_override:  # กรณีสร้าง record ใหม่
                self.line_ids = [(5, 0, 0)]
                self.ot_line_ids = [(5, 0, 0)]

    @api.depends('line_ids.amount', 'line_ids.type')
    def _compute_total(self):
        for rec in self:
            # ถ้าติ๊ก override_totals ไว้ → ไม่คำนวณใหม่ ใช้ค่าที่ user กำหนดเอง
            if rec.override_totals:
                continue
            rec.total_gross = sum(l.amount for l in rec.line_ids if l.type == 'income')
            rec.total_deduction = sum(l.amount for l in rec.line_ids if l.type == 'deduction')
            rec.net_salary = rec.total_gross - rec.total_deduction

    @api.depends('employee_id', 'payment_date')
    def _compute_other_income_total(self):
        """
        ดึงยอดรวมเงินได้อื่นๆ จาก other.income.line
        โดยเลือกเฉพาะรายการที่ยืนยันแล้ว (state == 'confirmed')
        และวันที่จ่ายเงินของบรรทัดอยู่ในเดือน/ปี เดียวกับ payment_date ของ payroll.salary
        ถ้ายอด other_income_total > income_other → auto-bump income_other ให้เท่ากัน
        """
        for rec in self:
            total = 0.0
            if rec.employee_id and rec.payment_date:
                pd = rec.payment_date
                start_month = pd.replace(day=1)
                last_day = calendar.monthrange(pd.year, pd.month)[1]
                end_month = pd.replace(day=last_day)

                lines = self.env['other.income.line'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', '=', 'confirmed'),
                    ('payment_date', '>=', start_month),
                    ('payment_date', '<=', end_month),
                ])
                total = sum(l.amount for l in lines)
            rec.other_income_total = total
            # auto-bump income_other ถ้าต่ำกว่ายอดเงินได้อื่นๆ
            if total > 0 and (rec.income_other or 0.0) < total:
                rec.income_other = total

    @api.constrains('income_other', 'other_income_total')
    def _check_income_other_min(self):
        """รายได้อื่นๆ ต้องไม่ต่ำกว่า เงินได้อื่นๆ ที่ดึงมา"""
        for rec in self:
            if (rec.income_other or 0.0) < (rec.other_income_total or 0.0):
                raise ValidationError(
                    "รายได้อื่นๆ (%.2f) ต้องไม่ต่ำกว่าเงินได้อื่นๆ (%.2f)" % (
                        rec.income_other or 0.0,
                        rec.other_income_total or 0.0,
                    )
                )

    @api.onchange('income_other')
    def _onchange_income_other_min(self):
        """กันไม่ให้ user พิมพ์ค่าต่ำกว่ายอดเงินได้อื่นๆ ที่ดึงมา (แจ้งเตือน + ดีดค่ากลับ)"""
        if self.other_income_total and (self.income_other or 0.0) < self.other_income_total:
            minimum = self.other_income_total
            self.income_other = minimum
            return {
                'warning': {
                    'title': 'ไม่สามารถกำหนดค่าต่ำกว่าเงินได้อื่นๆ',
                    'message': 'รายได้อื่นๆ ต้องมากกว่าหรือเท่ากับ %.2f (ยอดจากเมนูเงินได้อื่นๆ)' % minimum,
                }
            }

    def _inverse_total_gross(self):
        """ให้ user แก้ไข total_gross ได้ตรงๆ"""
        for rec in self:
            if rec.override_totals:
                _logger.info("[OVERRIDE] total_gross set to %s for payroll %s", rec.total_gross, rec.id)

    def _inverse_total_deduction(self):
        """ให้ user แก้ไข total_deduction ได้ตรงๆ"""
        for rec in self:
            if rec.override_totals:
                _logger.info("[OVERRIDE] total_deduction set to %s for payroll %s", rec.total_deduction, rec.id)

    def _inverse_net_salary(self):
        """ให้ user แก้ไข net_salary ได้ตรงๆ"""
        for rec in self:
            if rec.override_totals:
                _logger.info("[OVERRIDE] net_salary set to %s for payroll %s", rec.net_salary, rec.id)

    @api.depends('ot_total_weekday', 'ot_total_holiday', 'ot_total_sunday')
    def _compute_summary_totals(self):
        for rec in self:
            rec.ot_total = rec.ot_total_weekday + rec.ot_total_holiday + rec.ot_total_sunday
            rec.sso_total = sum(l.amount for l in rec.line_ids if l.name == 'ประกันสังคม')

    @api.depends('total_gross', 'personal_deduction', 'expense_deduction',
                 'provident_fund_rate', 'sso_total', 'tax_bracket_ids', 'line_ids')
    def _compute_tax(self):
        for rec in self:
            tax_line = rec.line_ids.filtered(lambda l: l.name == 'ภาษีหัก ณ ที่จ่าย')
            if tax_line and tax_line.amount > 0:  # ✅ ใช้ค่าที่ user override
                rec.tax_monthly = tax_line.amount
                rec.tax_annual = rec.tax_monthly * 12
            else:
                sso_amount_monthly = rec.sso_total or 0.0
                # ❌ เดิม: ใช้ rec.total_gross → รวมสะสม
                # ✅ ใหม่: ใช้ base_salary + OT ของเดือนนี้
                monthly_income = rec.base_salary + rec.ot_total
                rec.tax_monthly, rec.tax_annual = rec._calculate_tax(monthly_income, sso_amount_monthly)

    def _calculate_tax(self, gross_income, sso_monthly):
        annual_income = gross_income * 12
        sso_annual = min(sso_monthly * 12, 9000)

        provident_fund_annual = 0
        if self.provident_fund_rate > 0:
            provident_fund_monthly = self.base_salary * (self.provident_fund_rate / 100)
            provident_fund_annual = min(provident_fund_monthly * 12, self.provident_fund_deduction_max)

        # ✅ ค่าใช้จ่ายมาตรฐาน
        expense_deduction_effective = min(annual_income * 0.5, self.expense_deduction)

        total_deduction = (
                self.personal_deduction +
                expense_deduction_effective +
                sso_annual +
                provident_fund_annual
        )

        net_taxable_income = max(0, annual_income - total_deduction)

        annual_tax = 0
        for bracket in sorted(self.tax_bracket_ids, key=lambda b: b.sequence, reverse=True):
            if net_taxable_income > bracket.income_from:
                annual_tax = (net_taxable_income * (bracket.rate / 100.0)) - bracket.deduction
                break

        # ❌ ไม่ปัดเศษ
        monthly_tax = annual_tax / 12

        return monthly_tax, annual_tax

    def action_generate_next_month(self):
        for rec in self:
            current_date = datetime.date(int(rec.year), rec.month, 1)
            next_date = current_date + relativedelta(months=1)
            existing_payroll = self.env['payroll.salary'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('month', '=', next_date.month),
                ('year', '=', str(next_date.year)),
            ], limit=1)
            if not existing_payroll:
                new_payroll = rec.copy({
                    'month': next_date.month,
                    'year': str(next_date.year),
                    'line_ids': [],
                    'ot_line_ids': [],
                })
                # Find the previous payroll record based on the new record's employee_id, and the month/year of the record we are copying from
                prev_payroll = self.env['payroll.salary'].search([
                    ('employee_id', '=', new_payroll.employee_id.id),
                    ('month', '=', rec.month),
                    ('year', '=', str(rec.year)),
                ], limit=1)

                # Set accumulated values based on previous record
                if prev_payroll:
                    new_payroll.accumulated_income = prev_payroll.accumulated_income + new_payroll.base_salary
                    new_payroll.accumulated_vat = prev_payroll.accumulated_vat + new_payroll.tax_monthly
                    new_payroll.accumulated_social_security = prev_payroll.accumulated_social_security + new_payroll.sso_total
                    _logger.info("Found previous payroll record. Accumulated values: income=%s, vat=%s, sso=%s",
                                 new_payroll.accumulated_income, new_payroll.accumulated_vat,
                                 new_payroll.accumulated_social_security)
                else:
                    new_payroll.accumulated_income = new_payroll.base_salary
                    new_payroll.accumulated_vat = new_payroll.tax_monthly
                    new_payroll.accumulated_social_security = new_payroll.sso_total
                    _logger.info(
                        "No previous payroll record found. Initial accumulated values: income=%s, vat=%s, sso=%s",
                        new_payroll.accumulated_income, new_payroll.accumulated_vat,
                        new_payroll.accumulated_social_security)

                new_payroll._onchange_employee_id()
        return True

    def action_recalculate_all(self):
        for rec in self:
            rec._onchange_employee_id()
        return True


class PayrollTaxBracket(models.Model):
    _name = 'payroll.tax.bracket'
    _description = 'ขั้นบันไดอัตราภาษี'
    _order = 'sequence'
    payroll_id = fields.Many2one('payroll.salary', string='Payroll', ondelete='cascade')
    sequence = fields.Integer(string='ลำดับ', required=True)
    income_from = fields.Float(string='เงินได้ตั้งแต่', required=True)
    income_to = fields.Float(string='ถึง', required=True)
    rate = fields.Float(string='อัตราภาษี (%)', required=True)
    deduction = fields.Float(string='ค่าลดหย่อนภาษีของขั้น',
                             help="ค่าที่ใช้ในสูตรคำนวณแบบย่อ: (เงินได้สุทธิ * อัตราภาษี) - ค่านี้")


class PayrollSalaryLine(models.Model):
    _name = "payroll.salary.line"
    _description = "รายละเอียดเงินเดือน"
    payroll_id = fields.Many2one("payroll.salary", string="Payroll", required=True, ondelete="cascade")
    name = fields.Char(string="รายการ")
    type = fields.Selection([('income', 'รายได้'), ('deduction', 'รายการหัก')], string="ประเภทรายการ", required=True)
    amount = fields.Float(string="จำนวนเงิน", required=True)


class PayrollOtLine(models.Model):
    _name = 'payroll.ot.line'
    _description = 'รายการคำนวณ OT'
    _order = 'date'

    payroll_id = fields.Many2one('payroll.salary', string='Payroll', ondelete='cascade')
    date = fields.Date(string='วันที่')
    start_time = fields.Datetime(string='เวลาเริ่มต้น')
    end_time = fields.Datetime(string='เวลาสิ้นสุด')

    start_time_x = fields.Char(string='เวลาเริ่มต้น')
    end_time_x = fields.Char(string='เวลาสิ้นสุด')

    ot_hours = fields.Float(string='ชั่วโมง OT (ทศนิยม)')
    ot_amount = fields.Float(string='จำนวนเงิน')

    # ประเภท OT
    ot_type = fields.Selection([
        ('weekday', 'ค่าล่วงเวลา/โอที (1.5 เท่า)'),
        ('holiday', 'ค่าล่วงเวลา/วันหยุดนักขัตฤกษ์ (2.0 เท่า)'),
        ('sunday', 'ค่าล่วงเวลา (1.0 เท่า)'),
    ], string="ประเภท OT", required=True, default='weekday')

    rate_multiplier = fields.Float(string='อัตรา (เท่า)', compute='_compute_rate', store=True)

    @api.depends('ot_type')
    def _compute_rate(self):
        for line in self:
            if line.ot_type == 'weekday':
                line.rate_multiplier = 1.5
            elif line.ot_type == 'holiday':
                line.rate_multiplier = 2.0
            elif line.ot_type == 'sunday':
                line.rate_multiplier = 1.0
            else:
                line.rate_multiplier = 1.0
