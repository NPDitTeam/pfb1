# -*- coding: utf-8 -*-

import requests
import json
from odoo import models, fields, api, _
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
    child_deduction = fields.Float(
        string="ค่าลดหย่อนบุตร", default=0.0,
        help="ใส่ยอดรวมค่าลดหย่อนบุตรต่อปี (กรอกเอง) — บุตรคนละ 30,000 บาท/ปี "
             "(คนที่ 2 เป็นต้นไปที่เกิดปี 2561+ ได้ 60,000) "
             "ระบบจะหักออกจากเงินได้ก่อนคำนวณภาษี เหมือนค่าลดหย่อนส่วนตัว")

    # ════════════════ ค่าลดหย่อนภาษีเพิ่มเติม (กรอกยอดเองต่อปี) ════════════════
    # ทุกช่องด้านล่างจะถูกรวมหักออกจากเงินได้ก่อนคำนวณภาษี (ดู EXTRA_DEDUCTION_FIELDS)
    # ── กลุ่มครอบครัว ──
    ded_spouse = fields.Float(
        string="คู่สมรส (ไม่มีเงินได้)", default=0.0, help="สูงสุด 60,000")
    ded_parents = fields.Float(
        string="อุปการะบิดามารดา", default=0.0,
        help="คนละ 30,000 (อายุ 60 ปีขึ้นไป) สูงสุด 4 คน = 120,000")
    ded_disabled = fields.Float(
        string="อุปการะผู้พิการ/ทุพพลภาพ", default=0.0, help="คนละ 60,000")
    # ── กลุ่มประกัน ──
    ded_life_insurance = fields.Float(
        string="เบี้ยประกันชีวิต", default=0.0,
        help="สูงสุด 100,000 (รวมประกันสุขภาพตนเองแล้วไม่เกิน 100,000)")
    ded_health_insurance = fields.Float(
        string="เบี้ยประกันสุขภาพตนเอง", default=0.0,
        help="สูงสุด 25,000 และรวมกับประกันชีวิตไม่เกิน 100,000")
    ded_parents_health_insurance = fields.Float(
        string="เบี้ยประกันสุขภาพบิดามารดา", default=0.0, help="สูงสุด 15,000")
    ded_pension_insurance = fields.Float(
        string="เบี้ยประกันชีวิตแบบบำนาญ", default=0.0,
        help="สูงสุด 15% ของเงินได้ และไม่เกิน 200,000")
    # ── กลุ่มการลงทุน/เกษียณ (เพดานรวมกลุ่มเกษียณ 500,000) ──
    ded_rmf = fields.Float(
        string="กองทุน RMF", default=0.0, help="สูงสุด 30% ของเงินได้ และไม่เกิน 500,000")
    ded_ssf = fields.Float(
        string="กองทุน SSF", default=0.0, help="สูงสุด 30% ของเงินได้ และไม่เกิน 200,000")
    ded_thaiesg = fields.Float(
        string="กองทุน ThaiESG", default=0.0, help="สูงสุด 30% ของเงินได้ และไม่เกิน 300,000")
    ded_pension_fund = fields.Float(
        string="กองทุนสำรองเลี้ยงชีพ/กบข./ครู (เพิ่มเติม)", default=0.0,
        help="กรอกเพิ่มถ้าไม่ได้คิดจากอัตรา % ด้านล่าง — สูงสุด 15% และไม่เกิน 500,000")
    # ── กลุ่มอื่นๆ ──
    ded_home_loan_interest = fields.Float(
        string="ดอกเบี้ยกู้ยืมซื้อที่อยู่อาศัย", default=0.0, help="สูงสุด 100,000")
    ded_donation = fields.Float(
        string="เงินบริจาคทั่วไป", default=0.0,
        help="กรอกยอดที่หักได้จริง (ไม่เกิน 10% ของเงินได้หลังหักลดหย่อนอื่น)")
    ded_donation_education = fields.Float(
        string="เงินบริจาคการศึกษา/กีฬา/รพ.รัฐ (2 เท่า)", default=0.0,
        help="กรอกยอดที่หักได้จริงหลังคูณ 2 แล้ว (รวมแล้วไม่เกิน 10% ของเงินได้)")
    ded_shopping = fields.Float(
        string="ช้อปดีมีคืน / Easy E-Receipt", default=0.0, help="สูงสุด 50,000")

    # รายชื่อช่องลดหย่อนเพิ่มเติม (กรอกเอง) — ใช้รวมยอดใน _calculate_tax
    EXTRA_DEDUCTION_FIELDS = [
        'ded_spouse', 'ded_parents', 'ded_disabled',
        'ded_life_insurance', 'ded_health_insurance',
        'ded_parents_health_insurance', 'ded_pension_insurance',
        'ded_rmf', 'ded_ssf', 'ded_thaiesg', 'ded_pension_fund',
        'ded_home_loan_interest', 'ded_donation', 'ded_donation_education',
        'ded_shopping',
    ]

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
    line_ids = fields.One2many("payroll.salary.line", "payroll_id", string="รายละเอียดเงินเดือน")
    
    # ✅ เพิ่ม flag สำหรับ override ยอดรวม
    override_totals = fields.Boolean(string="ปรับแก้ยอดรวมด้วยมือ", default=False)

    # ✅ ยอดรวม "เงินได้อื่นๆ" จากเมนู other.income ของเดือนเดียวกันกับ payment_date
    other_income_total = fields.Float(
        string="เงินได้อื่นๆ",
        compute="_compute_other_income_total",
        store=True,
        readonly=True,
        help="ยอดรวมเงินได้อื่นๆ ที่ยืนยันแล้ว และวันที่จ่ายเงินอยู่ในเดือนเดียวกับวันที่จ่ายเงินในรายการเงินเดือนนี้ (รวมค่าตัวนักแสดงด้วย)",
    )

    # ✅ ยอดค่าตัวนักแสดง ถ่าย content จาก hr.manual.time.log ของรอบตัดเงินเดือน
    actor_content_total = fields.Float(
        string="ค่าตัวนักแสดง ถ่าย content",
        compute="_compute_actor_content_total",
        store=True,
        readonly=True,
        help="ยอดรวม 'จำนวนเงิน' จาก hr.manual.time.log ที่ reason_type='ค่าตัวนักแสดง ถ่าย content' "
             "และ work_date อยู่ในช่วงตัดรอบเงินเดือน",
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
    missed_days_detail = fields.Text(string='รายละเอียดวันขาดงาน', readonly=True)
    deduction_detail = fields.Text(
        string='รายละเอียดการหัก (สาย/ขาด/ออกก่อน/ลา)', readonly=True,
        help='แจกแจงรายการที่หักแต่ละวัน เพื่อตรวจสอบ')
    deduction_line_ids = fields.One2many(
        'payroll.deduction.line', 'payroll_id',
        string='รายละเอียดการหัก (แจกแจงรายวัน)', readonly=True,
        help='ตารางแจกแจงว่าหักอะไร เท่าไหร่ วันที่/เวลาไหน เพื่อให้ตรวจสอบง่าย')
    late_checkin_deduction = fields.Float(string='ยอดหักสาย', readonly=True)
    early_checkout_deduction = fields.Float(string='ยอดหักออกก่อนเวลา', readonly=True)
    missed_days_deduction = fields.Float(string='ยอดหักขาดงาน', readonly=True)
    lateness_deduction = fields.Float(string='ยอดหักรวม', readonly=True)
    cutoff_day = fields.Integer(string='วันตัดรอบ', default=24, required=True)
    leave_deduction_total = fields.Float(string='ยอดหักจากการลา', readonly=True)

    ot_total = fields.Float(string="ค่าล่วงเวลา (OT) รวม", compute='_compute_summary_totals', store=True)
    sso_total = fields.Float(
        string="ประกันสังคม/เดือน",
        compute="_compute_sso_total",
        inverse="_inverse_sso_total",  # ✅ เพิ่ม inverse
        store=True
    )
    # ประกันสังคมต่อปี (= ต่อเดือน × 12) — ยอดที่ใช้ลดหย่อนภาษี
    sso_annual_used = fields.Float(
        string="ประกันสังคม/ปี (ใช้ลดหย่อนภาษี)",
        compute="_compute_sso_annual_used", store=True, readonly=True)
    payment_date = fields.Date(
        string="วันที่จ่ายเงิน",
        default=lambda self: self._get_default_date_28()
    )
    # ✅ ยอดต้นรอบ — ใส่เฉพาะเดือนแรกที่ย้ายมาจากระบบเก่า (default 0 = เริ่มจากศูนย์)
    # ระบบจะ: accumulated = opening + total_gross เดือนนี้
    # เดือนถัดไประบบจะใช้ prev.accumulated + total_gross อัตโนมัติ
    opening_accumulated_income = fields.Float(
        string="รายรับสะสมต้นรอบ", default=0.0,
        help="ใส่ยอดรายได้สะสมจากระบบเก่า (ไม่รวมเดือนนี้) — เฉพาะเดือนแรกที่ย้ายเข้าระบบ")
    opening_accumulated_vat = fields.Float(
        string="ภาษีสะสมต้นรอบ", default=0.0,
        help="ใส่ยอดภาษีสะสมจากระบบเก่า (ไม่รวมเดือนนี้)")
    opening_accumulated_social_security = fields.Float(
        string="ปกส.สะสมต้นรอบ", default=0.0,
        help="ใส่ยอดประกันสังคมสะสมจากระบบเก่า (ไม่รวมเดือนนี้)")

    # ประเภทการโอนเงิน — ดึงจาก employee.salary (อัพเดทเมื่อกด "คำนวณใหม่")
    transfer_type = fields.Selection(
        related='employee_id.transfer_type', store=True, readonly=True,
        string='ประเภทการโอนเงิน')

    # ❌ deprecated — ไม่ใช้แล้ว เก็บไว้กันข้อมูลเก่าหาย
    manual_override_accumulated = fields.Boolean(
        string="ปรับค่าสะสมเอง (legacy)", default=False)
    accumulated_income = fields.Float(
        string="รายรับสะสม",
        compute="_compute_accumulated_values",
        store=True, readonly=True
    )
    accumulated_vat = fields.Float(
        string="ภาษีสะสม",
        compute="_compute_accumulated_values",
        store=True, readonly=True
    )
    accumulated_social_security = fields.Float(
        string="ประกันสังคมสะสม",
        compute="_compute_accumulated_values",
        store=True, readonly=True
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
    income_allowance = fields.Float(string="เบี้ยเลี้ยง นอกสถานที่", default=0.0)
    income_food = fields.Float(string="ค่าอาหาร", default=0.0)
    income_transport = fields.Float(string="ค่าเดินทาง", default=0.0)
    # แยกย่อยของ "ค่าเดินทาง" — ดึงจาก vehicle.booking (odoo18) ทั้งคู่
    # income_transport = income_transport_trip + income_transport_allowance
    income_transport_trip = fields.Float(string="ค่าเที่ยวขนส่ง", default=0.0)
    income_transport_allowance = fields.Float(string="ค่าเบี้ยเลี้ยงขนส่ง", default=0.0)
    income_fuel = fields.Float(string="อินเซนทีฟ", default=0.0)
    income_commission = fields.Float(string="ค่าคอมมิชชั่นสาขา", default=0.0)
    income_commission_sale = fields.Float(string="ค่าคอมมิชชั่นSale", default=0.0)
    income_other = fields.Float(string="รายได้อื่นๆ (รวมทั้งหมด)", default=0.0,
                                help="ผลรวม: รายได้อื่นๆ (ใส่เพิ่ม) + ค่าตัวนักแสดง + โบนัส + เงินตกหล่น + เมนูเงินได้อื่นๆ "
                                     "(ใช้ในสลิปเงินเดือนเป็น line 'รายได้อื่นๆ')")
    income_other_manual = fields.Float(
        string="รายได้อื่นๆ (ใส่เพิ่ม)", default=0.0,
        help="ใส่ค่า free-form เพิ่มเติม ที่ไม่ใช่ค่าตัวนักแสดง / โบนัส / เงินตกหล่น"
    )
    # ตารางแสดงรายการที่ระบบดึงมาให้เห็นยอดที่เข้ามาในรายได้อื่นๆ
    other_income_breakdown_ids = fields.Many2many(
        'other.income.line', string="รายการเงินได้อื่นๆ (จากเมนู)",
        compute='_compute_other_income_breakdowns',
    )
    actor_content_breakdown_ids = fields.Many2many(
        'hr.manual.time.log', string="รายการค่าตัวนักแสดง ถ่าย content",
        compute='_compute_other_income_breakdowns',
    )

    # โบนัส — เฉพาะเดือนนี้, ติ๊กเพื่อใช้, เดือนใหม่ default = ไม่ติ๊ก (auto reset)
    income_bonus = fields.Float(string="โบนัส", default=0.0)
    bonus_active = fields.Boolean(
        string="ใช้โบนัสเดือนนี้", default=False,
        help="ติ๊กเพื่อให้โบนัสนับรวมเงินเดือนเดือนนี้ "
             "เดือนถัดไประบบจะ default = ไม่ติ๊ก (ไม่นับ) อัตโนมัติ"
    )

    # เงินตกหล่นจากรอบเงินเดือน — ใส่ต่อเดือน, เดือนใหม่ default = 0, ค่าเก่าเก็บใน record เดิม
    income_missed_payment = fields.Float(
        string="เงินตกหล่นจากรอบเงินเดือน", default=0.0,
        help="เงินที่ตกหล่นจากรอบก่อนหน้า — แต่ละ payroll record มีค่าของเดือนนั้น "
             "(เดือนถัดไป default = 0, ดูประวัติได้จากรอบเก่า)"
    )

    # รายจ่ายใหม่
    expense_provident = fields.Float(string="กองทุนสำรองเลี้ยงชีพ", default=0.0)
    expense_advance = fields.Float(string="เบิกเงินล่วงหน้า", default=0.0)
    expense_loan = fields.Float(string="เงินกู้", default=0.0)
    expense_ksl = fields.Float(string="กยศ", default=0.0)
    expense_insurance = fields.Float(string="เงินประกันการทำงาน (ไม่ใช้แล้ว)", default=0.0,
                                     help="Deprecated — ย้าย logic ไปที่ expense_other / income_other")
    expense_other = fields.Float(string="หักอื่นๆ (รวมทั้งหมด)", default=0.0,
                                 compute='_compute_expense_other_total', store=True,
                                 help="ผลรวม: หักอื่นๆ (ใส่เพิ่ม) + หักรายเดือน + หัก Work Permit (จาก work.security.deposit)")
    expense_other_manual = fields.Float(
        string="หักอื่นๆ (ใส่เพิ่ม)", default=0.0,
        help="ใส่ค่า free-form เพิ่มเติม ที่ไม่ใช่จาก work.security.deposit"
    )

    # ✅ ยอดหักจาก work.security.deposit แยกตามประเภท
    expense_deposit_regular_total = fields.Float(
        string="หักรายเดือน (จาก work.security.deposit)",
        compute='_compute_deposit_amounts', store=True,
    )
    expense_deposit_extra_total = fields.Float(
        string="หัก Work Permit / อื่นๆ (จาก work.security.deposit)",
        compute='_compute_deposit_amounts', store=True,
    )
    income_deposit_refund_total = fields.Float(
        string="คืนเงินประกันรายเดือน (จาก work.security.deposit)",
        compute='_compute_deposit_amounts', store=True,
        help="ถ้าพนักงานลาออกในเดือนนี้ → คืนเงินประกัน regular ที่หักไปแล้ว",
    )
    # ตารางแสดงรายการ deposit ที่ดึงมา (สำหรับ view)
    expense_deposit_regular_breakdown_ids = fields.Many2many(
        'work.security.deposit.line.payment', relation='payroll_deposit_regular_rel',
        string="รายการหักรายเดือน",
        compute='_compute_deposit_amounts',
    )
    expense_deposit_extra_breakdown_ids = fields.Many2many(
        'work.security.deposit.line.payment', relation='payroll_deposit_extra_rel',
        string="รายการหัก Work Permit / อื่นๆ",
        compute='_compute_deposit_amounts',
    )
    income_deposit_refund_breakdown_ids = fields.Many2many(
        'work.security.deposit.line', string="รายการคืนเงินประกัน (พนักงานลาออก)",
        compute='_compute_deposit_amounts',
    )

    # แยก ขาด-ลา-สาย
    deduction_late = fields.Float(string="สาย", default=0.0)
    deduction_leave = fields.Float(string="ลากิจ", default=0.0)
    deduction_absent = fields.Float(string="ขาดงาน", default=0.0)
    manual_override = fields.Boolean(string="ปรับแก้ด้วยมือ", default=False)

    # ✅ ปรับแก้ด้วยมือ ฝั่ง "รายได้" (แยกจากฝั่งรายจ่าย/หัก)
    # ติ๊กแล้ว → ไม่ดึงค่าคอม (สาขา/Sale) จาก API มาทับ ยึดค่าที่กรอกเอง
    # แต่ส่วนอื่นยังคำนวณอัตโนมัติ (line_ids ยังถูก rebuild → ค่าคอมที่กรอกไหลเข้ายอดรวม)
    manual_override_income = fields.Boolean(string="ปรับแก้ด้วยมือ", default=False)

    # ✅ ปรับแก้ด้วยมือ เฉพาะ "ภาษีหัก ณ ที่จ่าย" (แยกจากฝั่งรายจ่าย)
    # ติ๊กแล้ว → กรอกค่าภาษีที่ช่อง manual_tax_amount → ระบบยึดค่านี้ ไม่คำนวณทับ
    # ส่วนอื่นยังคำนวณอัตโนมัติปกติ
    manual_override_tax = fields.Boolean(string="ปรับแก้ด้วยมือ", default=False)
    manual_tax_amount = fields.Float(string="ภาษีหัก ณ ที่จ่าย (กรอกเอง/เดือน)", default=0.0)
    # ช่องกรอกภาษีรายปีแบบธรรมดา (ไม่ใช่ computed) → กรอกแล้วไม่ถูกคำนวณทับ
    manual_tax_annual = fields.Float(string="ภาษี/ปี (กรอกเอง)", default=0.0)

    # ✅ ปรับแก้ด้วยมือ เฉพาะ "ประกันสังคม" (แยกจากฝั่งรายจ่าย)
    # ติ๊กแล้ว → กรอกค่า ปกส. ที่ช่อง manual_sso_amount → ระบบยึดค่านี้ ไม่คำนวณทับ
    # ส่วนอื่นยังคำนวณอัตโนมัติปกติ
    manual_override_sso = fields.Boolean(string="ปรับแก้ด้วยมือ", default=False)
    manual_sso_amount = fields.Float(string="ประกันสังคม (กรอกเอง/เดือน)", default=0.0)
    # ช่องกรอก ปกส. รายปีแบบธรรมดา (ไม่ใช่ computed) → กรอกแล้วระบบหาร 12 เป็นรายเดือนให้
    manual_sso_annual = fields.Float(string="ประกันสังคม/ปี (กรอกเอง)", default=0.0)

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

    @api.depends('line_ids.amount', 'line_ids.name', 'manual_sso_amount', 'manual_override_sso')
    def _compute_sso_total(self):
        for rec in self:
            if rec.manual_override_sso or (rec.manual_sso_amount and rec.manual_sso_amount > 0):
                # ติ๊ก "ปรับแก้ด้วยมือ" หรือกรอก ปกส. เอง → ยึดค่าที่กรอก
                rec.sso_total = rec.manual_sso_amount
            else:
                rec.sso_total = sum(l.amount for l in rec.line_ids if l.name == 'ประกันสังคม')

    @api.depends('sso_total')
    def _compute_sso_annual_used(self):
        for rec in self:
            rec.sso_annual_used = (rec.sso_total or 0.0) * 12

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
    # ✅ รายรับใช้ total_gross (รวม OT, โบนัส, ค่าครองชีพ, ฯลฯ) ตามมาตรฐาน กม. ภาษี
    # ✅ เดือนแรกของปี/เดือนแรกในระบบ → ใช้ opening balance + เดือนนี้
    @api.depends('employee_id', 'month', 'year', 'total_gross', 'tax_monthly', 'sso_total',
                 'opening_accumulated_income', 'opening_accumulated_vat',
                 'opening_accumulated_social_security')
    def _compute_accumulated_values(self):
        for rec in self:
            gross = rec.total_gross or 0.0
            tax = rec.tax_monthly or 0.0
            sso = rec.sso_total or 0.0

            # หา record ของ "เดือนก่อนหน้าในปีเดียวกัน"
            prev = self.env['payroll.salary'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('year', '=', rec.year),
                ('month', '<', rec.month),
            ], order='month desc', limit=1)

            if prev:
                # มีเดือนก่อนหน้า → ใช้สะสมจากเดือนก่อน + เดือนนี้
                rec.accumulated_income = prev.accumulated_income + gross
                rec.accumulated_vat = prev.accumulated_vat + tax
                rec.accumulated_social_security = prev.accumulated_social_security + sso
            else:
                # เดือนแรกในระบบ/ของปี → ใช้ opening balance + เดือนนี้
                # opening = 0 (default) → behave เหมือน reset เริ่มจากศูนย์
                # opening = ยอดจากระบบเก่า → ต่อยอดจากระบบเก่า
                rec.accumulated_income = (rec.opening_accumulated_income or 0.0) + gross
                rec.accumulated_vat = (rec.opening_accumulated_vat or 0.0) + tax
                rec.accumulated_social_security = (rec.opening_accumulated_social_security or 0.0) + sso

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

    def _get_prorated_salary_income(self):
        """คืนยอด "เงินเดือน" ที่ใช้เป็นรายได้ + ส่งไป PHP (สลิป)
        - ปกติ = base_salary เต็ม
        - ทำงานไม่ครบรอบ = base_salary ÷ 30 × จำนวนวัน(ปฏิทิน) ที่ทำงานจริงในรอบนี้
          ขอบเขตการทำงานจริง = [max(ต้นรอบ, วันเริ่มงาน) .. min(วันตัดรอบ, วันลาออก)]
          * เริ่มงานกลางรอบ → นับจากวันเริ่มงาน (ไม่ใช่ต้นรอบ)
          * ลาออกกลางรอบ → นับถึงวันลาออก (ลาออกวันตัดรอบ/หลัง = ทำครบ → ใช้ฐานเต็ม)
        ใช้กับ: บรรทัดรายได้เงินเดือน + ฐานคำนวณประกันสังคม (prorate ตามจริง)
        ⚠️ ภาษี/ยอดหักอื่นๆ ยังคิดจาก base_salary เต็ม
        """
        self.ensure_one()
        base = self.base_salary or 0.0
        resign_date = getattr(self.employee_id, 'resign_date', False)
        start_date = getattr(self.employee_id, 'start_date', False)
        # ไม่มีทั้งลาออกและวันเริ่มงาน → ฐานเต็ม (ทางลัด)
        if not resign_date and not start_date:
            return base
        try:
            m = int(self.month)
            y = int(self.year)
            end_day = self.cutoff_day or 24
            start_day = (self.period_id.cutoff_start_day if self.period_id else None) or 25
            last_end = calendar.monthrange(y, m)[1]
            cycle_end = date(y, m, min(end_day, last_end))
            if m == 1:
                prev_m, prev_y = 12, y - 1
            else:
                prev_m, prev_y = m - 1, y
            last_start = calendar.monthrange(prev_y, prev_m)[1]
            cycle_start = date(prev_y, prev_m, min(start_day, last_start))
            # ขอบเขตการทำงานจริงในรอบนี้
            eff_start = cycle_start
            if start_date and start_date > cycle_start:
                eff_start = start_date            # เริ่มงานกลางรอบ
            eff_end = cycle_end                   # วันตัดรอบ (ทำครบ)
            if resign_date and resign_date < cycle_end:
                eff_end = resign_date             # ลาออกกลางรอบ
            # ทำงานครบทั้งรอบ → ฐานเต็ม
            if eff_start <= cycle_start and eff_end >= cycle_end:
                return base
            days_worked = max(0, (eff_end - eff_start).days + 1)
            prorated = round(base / 30.0 * days_worked, 2)
            _logger.info("[SALARY PRORATE] emp=%s start=%s resign=%s eff=[%s..%s] days=%d base=%.2f -> %.2f",
                         self.employee_code, start_date, resign_date, eff_start, eff_end,
                         days_worked, base, prorated)
            return prorated
        except (TypeError, ValueError) as e:
            _logger.warning("[SALARY PRORATE] emp=%s: %s", self.employee_code, e)
        return base

    def _prepare_data_for_php(self):
        self.ensure_one()
        # ใช้ค่าที่ compute เก็บไว้แล้ว — รวม opening balance + ใช้ total_gross ตามมาตรฐาน
        accumulated_income = self.accumulated_income or 0.0
        accumulated_vat = self.accumulated_vat or 0.0
        accumulated_social_security = self.accumulated_social_security or 0.0

        payment_date_str = self.payment_date.strftime('%Y-%m-%d') if self.payment_date else None

        return {
            'odoo_id': self.id,
            'employee_id': self.employee_id.id,
            'employee_code': self.employee_code,
            # ✅ ส่งยอดเงินเดือนที่ prorate แล้ว (คนลาออกกลางรอบ) เพื่อให้สลิป (ดึงจาก PHP) ตรงกับ Odoo
            'base_salary': self._get_prorated_salary_income(),
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
            return api_response
        except requests.exceptions.RequestException as e:
            _logger.error(f"API Connection Error: {e}")
        except json.JSONDecodeError:
            _logger.error("JSON Decode Error: Response from API is not a valid JSON.")
        return None

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
        แบบ serial ใน cursor เดียวกับ transaction หลัก

        NOTE: เดิมใช้ threading (cursor แยก + cr.commit ต่อ thread) เพื่อความเร็ว
        แต่ไม่ปลอดภัย:
          - แต่ละ thread set commission → trigger write() → _populate_all_lines()
            ลบ+สร้าง line_ids ใหม่พร้อมกัน 3 thread บน record เดียว → ชนกัน/abort
            → thread fail เงียบ ๆ (catch ภายใน) → commission ไม่ถูกเขียน
            แต่ flow หลักยังขึ้น success → ค่า commission ค้าง stale
          - ตอน create() row ยังไม่ commit → thread มองไม่เห็น row → fetch พลาด
        จึงเปลี่ยนเป็น serial ให้ผลถูกต้องเสมอ (ช้ากว่าแต่เชื่อถือได้)
        """
        self.ensure_one()
        self._fetch_vehicle_booking_data()
        self._fetch_commission_branch_data()
        self._fetch_commission_sales_data()


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
            # ดึง API + populate ภายใต้ flag → ข้าม side-effect ของทุก field write
            # (กัน write-storm) แล้ว sync PHP + employee ครั้งเดียวตอนจบ
            rec_ctx = record.with_context(_skip_payroll_write_side_effects=True)
            rec_ctx._parallel_fetch_all()
            rec_ctx._populate_all_lines()
            _logger.info(
                "[CREATE] Payroll created for %s | Month: %s/%s | income=%s, vat=%s, sso=%s",
                record.employee_id.firstname, record.month, record.year,
                record.accumulated_income, record.accumulated_vat, record.accumulated_social_security
            )
            data = record._prepare_data_for_php()
            record._send_data_to_php_api('create', data)
            # sync sso/tax ของเดือนล่าสุด → employee.salary
            record._sync_latest_to_employee()
        return records

    def write(self, vals):
        res = super(PayrollSalary, self).write(vals)
        # ระหว่าง batch/recompute (create / refresh รอบ / _populate_all_lines)
        # จะตั้ง context นี้เพื่อข้าม side-effect ของทุก field write
        # (auto _populate_all_lines + ยิง PHP + sync employee) → กัน write-storm
        # ผู้เรียกจะ sync ครั้งเดียวตอนจบต่อคนเอง
        if self.env.context.get('_skip_payroll_write_side_effects'):
            return res
        for record in self:
            if not record.manual_override:
                # NOTE: income_other / expense_other เป็น computed (set โดย compute) → ห้ามใส่
                # มิฉะนั้น recurrsion: write → _populate_all_lines → compute → write income_other → ...
                if any(f in vals for f in [
                    'employee_id', 'ot_calculation_method', 'month', 'year', 'cutoff_day',
                    'income_allowance', 'income_food', 'income_transport',
                    'income_fuel', 'income_commission', 'income_commission_sale',
                    'income_other_manual', 'income_bonus', 'bonus_active', 'income_missed_payment',
                    'expense_provident', 'expense_advance', 'expense_loan',
                    'expense_ksl', 'expense_other_manual', 'child_deduction',
                    'manual_override_tax', 'manual_override_sso',
                    'manual_tax_amount', 'manual_sso_amount', 'manual_tax_annual',
                    'manual_sso_annual',
                    'ded_spouse', 'ded_parents', 'ded_disabled',
                    'ded_life_insurance', 'ded_health_insurance',
                    'ded_parents_health_insurance', 'ded_pension_insurance',
                    'ded_rmf', 'ded_ssf', 'ded_thaiesg', 'ded_pension_fund',
                    'ded_home_loan_interest', 'ded_donation',
                    'ded_donation_education', 'ded_shopping'
                ]):
                    record._populate_all_lines()

            # ข้าม sync PHP/employee ถ้า record ยังไม่ save (NewId — onchange context)
            # มิฉะนั้น json.dumps(odoo_id=NewId) จะ crash + ไม่มีประโยชน์ที่จะ sync record ที่ยังไม่มีจริง
            if isinstance(record.id, models.NewId):
                continue

            _logger.info(
                "[WRITE] Payroll updated for %s | Month: %s/%s | income=%s, vat=%s, sso=%s",
                record.employee_id.firstname, record.month, record.year,
                record.accumulated_income, record.accumulated_vat, record.accumulated_social_security
            )
            data = record._prepare_data_for_php()
            record._send_data_to_php_api('update', data)
            # sync sso_total / tax_monthly ของเดือนล่าสุด → employee.salary
            record._sync_latest_to_employee()
        return res

    def _sync_latest_to_employee(self):
        """ถ้า payroll นี้เป็นเดือน/ปีล่าสุดของพนักงาน → push ค่า sso_total + tax_monthly
        ไปอัพเดท employee.salary (ฟิลด์ ค่าคงที่ของประกันสังคม + จำนวนภาษีคงที่ต่อเดือน)
        เพื่อให้ข้อมูลพนักงานมีค่าล่าสุดเสมอ"""
        for rec in self:
            if not rec.employee_id or self.env.context.get('_skip_sync_to_employee'):
                continue
            # หา payroll ล่าสุดของพนักงานคนนี้
            latest = self.search([
                ('employee_id', '=', rec.employee_id.id),
            ], order='year desc, month desc', limit=1)
            if latest.id != rec.id:
                continue  # ไม่ใช่ล่าสุด → ไม่ update
            try:
                rec.employee_id.with_context(_skip_sync_to_employee=True).write({
                    'social_security_fixed_amount': rec.sso_total or 0.0,
                    'tax_exception': rec.tax_monthly or 0.0,
                })
                _logger.info(
                    "[SYNC→EMPLOYEE] emp=%s | sso=%.2f tax=%.2f (จาก payroll %s/%s)",
                    rec.employee_id.employee_code, rec.sso_total or 0.0, rec.tax_monthly or 0.0,
                    rec.month, rec.year,
                )
            except Exception as e:
                _logger.warning("[SYNC→EMPLOYEE] failed emp=%s: %s",
                                rec.employee_id.employee_code, e)

    @api.onchange(
        'income_allowance', 'income_food', 'income_transport',
        'income_fuel', 'income_commission', 'income_commission_sale',
        'income_other_manual', 'income_bonus', 'bonus_active', 'income_missed_payment',
        'expense_provident', 'expense_advance', 'expense_loan',
        'expense_ksl', 'expense_other_manual', 'child_deduction',
        'manual_tax_amount', 'manual_sso_amount', 'manual_override_sso',
        'ded_spouse', 'ded_parents', 'ded_disabled',
        'ded_life_insurance', 'ded_health_insurance',
        'ded_parents_health_insurance', 'ded_pension_insurance',
        'ded_rmf', 'ded_ssf', 'ded_thaiesg', 'ded_pension_fund',
        'ded_home_loan_interest', 'ded_donation',
        'ded_donation_education', 'ded_shopping'
    )
    def _onchange_income_expense_fields(self):
        if self:
            # บังคับ recompute computes ก่อน → set income_other / expense_other = total ทันที
            self._compute_deposit_amounts()
            self._compute_other_income_total()
            self._compute_expense_other_total()
            self._populate_all_lines()

    def _auto_tax_annual(self):
        """ภาษี/ปี ที่ระบบ "ควรคำนวณได้" ตามสูตร (ไม่สนค่าที่กรอกเอง) — ใช้เติมค่าเริ่มต้น"""
        self.ensure_one()
        exec_cfg = self.EXECUTIVE_TAX_CONFIG.get(self.employee_code or '')
        if exec_cfg and exec_cfg.get('tax_monthly') is not None:
            return (exec_cfg['tax_monthly'] or 0.0) * 12
        sso_m = self.sso_total or 0.0
        recurring, one_time = self._get_tax_income_base()
        _, auto_annual = self._calculate_tax(recurring, sso_m, one_time)
        return auto_annual

    @api.onchange('manual_override_tax')
    def _onchange_manual_override_tax(self):
        """ติ๊ก "ปรับแก้ด้วยมือ" (ภาษี) → เติมค่าภาษีที่ระบบคำนวณได้ให้เป็นค่าเริ่มต้น แล้วแก้ต่อได้
        ⚠️ ใช้ _auto_tax_annual (สูตร) ไม่ใช่ tax_monthly เพราะตอนนี้สลับเป็นโหมดมือแล้ว
        tax_monthly จะอ่านได้ = manual_tax_amount (= 0) ทำให้เติม 0"""
        for rec in self:
            if rec.manual_override_tax and not rec.manual_tax_amount:
                rec.manual_tax_amount = rec._auto_tax_annual() / 12.0
            rec._populate_all_lines()

    def _auto_sso_amount(self):
        """ประกันสังคมต่อเดือน ที่ระบบ "ควรคำนวณได้" ตามสูตร (ไม่สนค่าที่กรอกเอง)"""
        self.ensure_one()
        exec_cfg = self.EXECUTIVE_TAX_CONFIG.get(self.employee_code or '')
        if exec_cfg and exec_cfg.get('skip_sso'):
            return 0.0
        # ✅ คิดประกันสังคมจาก "เงินเดือนที่ได้จริง" (prorate ถ้าทำงานไม่เต็มเดือน)
        #    เต็มเดือน = base_salary เต็ม | ไม่เต็มเดือน = ยอด prorate (เช่น 10,400 → 520)
        sso_base = max(self.sso_min_wage, min(self._get_prorated_salary_income(), self.sso_max_wage))
        return float(round_half_up(sso_base * (self.sso_rate / 100.0)))

    @api.onchange('manual_sso_annual')
    def _onchange_manual_sso_annual(self):
        """กรอก "ประกันสังคม/ปี (กรอกเอง)" — ช่องธรรมดา (ไม่ถูกคำนวณทับ)
        - ใส่ค่า (> 0) → ตั้ง ปกส./เดือน = ปี ÷ 12 → ระบบยึดค่านี้
        - ลบเป็น 0/ว่าง → กลับไปคำนวณอัตโนมัติ"""
        for rec in self:
            if rec.manual_sso_annual and rec.manual_sso_annual > 0:
                rec.manual_sso_amount = rec.manual_sso_annual / 12.0
            else:
                rec.manual_sso_amount = 0.0
            rec._populate_all_lines()

    def _get_sales_commission_rate(self, total_net_rental, comm_type='sale_branch'):
        """คำนวณอัตราคอมมิชชั่น Sales ตามขั้นบันได (ดึงจากเมนูตั้งค่า)
        comm_type: 'sale_branch' (Sales สาขา) หรือ 'sale_headoffice' (Sales สำนักงานใหญ่)
        — กรอง config ตามประเภท เพราะอัตราขั้นบันไดของแต่ละประเภทไม่เหมือนกัน"""
        configs = self.env['commission.rate.config'].search(
            [('comm_type', '=', comm_type)], order='min_amount desc')
        for config in configs:
            if total_net_rental >= config.min_amount:
                return config.rate
        return 0.0

    # ✅ Sales สำนักงานใหญ่ (กรณีพิเศษ): ต้องมียอดรวม "เกิน" ยอดนี้ ถึงจะคิดค่าคอม
    SALES_HEADOFFICE_MIN = 100000.0

    def _sales_commission_rate_amount(self, total_net_rental, comm_type):
        """คืน (rate, amount) ค่าคอม Sales — ใช้ร่วมทั้ง calc และ popup ให้ตรงกันเสมอ
        - Sales สำนักงานใหญ่ (sale_headoffice): ต้องมียอดรวม "เกิน" 100,000 ถึงจะคิด
          (<= 100,000 → rate 0, amount 0) — gate เฉพาะ สนญ. เท่านั้น
        - Sales สาขา (sale_branch): คิดตาม rate config ขั้นบันไดเดิม ไม่มี gate
        """
        rate = self._get_sales_commission_rate(total_net_rental, comm_type)
        if comm_type == 'sale_headoffice' and total_net_rental <= self.SALES_HEADOFFICE_MIN:
            return 0.0, 0.0
        return rate, total_net_rental * (rate / 100.0)

    def _get_sale_commission_type(self):
        """คืนประเภทค่าคอม Sale ของพนักงานคนนี้:
        ถ้าอยู่ในรายชื่อ "จัดการค่าคอม Sales สำนักงานใหญ่" → 'sale_headoffice'
        ไม่อยู่ → 'sale_branch'"""
        self.ensure_one()
        is_ho = self.env['commission.sale.headoffice'].is_headoffice_employee(self.employee_id)
        return 'sale_headoffice' if is_ho else 'sale_branch'

    def _fetch_vehicle_booking_data(self):
        """
        ดึงค่าเที่ยว (travel_expenses) และค่าเบี้ยเลี้ยง (daily_allowance)
        จาก API https://npd-solution.com/api/vehicle-booking (DB: NPD_Logistics)
        เงื่อนไข:
          - state = 'done' (เสร็จสิ้น) — ฝั่ง API บังคับ
          - driver_id.employee_code = self.employee_id.employee_code (จับคู่ด้วยรหัสพนักงาน HR)
          - planned_end_date_t (วันเวลาส่งจริง) อยู่ใน "รอบตัดเงินเดือน" (25 เดือนก่อน ถึง 24 เดือนนี้)
            * ถ้าไม่มีวันส่งจริง fallback ใช้ planned_start_date_t กันงานตกหล่น
        → income_transport_trip = ค่าเที่ยว, income_transport_allowance = เบี้ยเลี้ยงขนส่ง
          income_transport (ค่าเดินทาง) = ค่าเที่ยวขนส่ง + ค่าเบี้ยเลี้ยงขนส่ง
          (ไม่แตะ income_allowance — เป็นของ HR hook payroll_allowance.py)

        หมายเหตุ: API กรองดึงข้อมูลด้วย planned_start_date_t เป็น calendar month (1-31)
        จึงเรียก API 2 รอบ (เดือน N-1 และ N) ให้ครอบคลุม แล้วค่อยกรองรอบตัดด้วย
        planned_end_date_t ในฝั่ง Python (เพราะงานส่งจริงมักวันเดียวกับวันออกเดินทาง)
        """
        self.ensure_one()

        if not self.employee_id or not self.month or not self.year:
            return

        from datetime import datetime as _dt, timedelta as _td
        # ✅ match ด้วยรหัสพนักงาน HR — แม่นกว่าชื่อ (กันชื่อสะกดต่าง/มีคำนำหน้า)
        emp_code = (self.employee_id.employee_code or '').strip()
        emp_fullname = ((self.firstname or '') + ' ' + (self.lastname or '')).strip()
        if not emp_code:
            _logger.warning("[VEHICLE BOOKING] พนักงาน %s ไม่มี employee_code → ข้าม", emp_fullname)
            return

        # ✅ คำนวณ "รอบตัดเงินเดือน" — ตรงกับวิธีของ _get_prorated_salary_income
        try:
            m = int(self.month)
            y = int(self.year)
        except (TypeError, ValueError):
            return
        end_day = self.cutoff_day or 24
        start_day = (self.period_id.cutoff_start_day if self.period_id else None) or 25
        last_end = calendar.monthrange(y, m)[1]
        cycle_end = date(y, m, min(end_day, last_end))
        if m == 1:
            prev_m, prev_y = 12, y - 1
        else:
            prev_m, prev_y = m - 1, y
        last_start = calendar.monthrange(prev_y, prev_m)[1]
        cycle_start = date(prev_y, prev_m, min(start_day, last_start))

        _logger.info("=" * 60)
        _logger.info("[VEHICLE BOOKING] เริ่มดึงค่าเที่ยว/เบี้ยเลี้ยง driver='%s' (code=%s) | รอบตัด=[%s..%s]",
                     emp_fullname, emp_code, cycle_start, cycle_end)

        login_url = 'https://npd-solution.com/web/session/authenticate'
        api_url = 'https://npd-solution.com/api/vehicle-booking'
        login_db = 'NPD_Logistics'
        login_user = 'Npd_admin'
        login_pass = '1234'

        total_travel_expenses = 0.0
        total_daily_allowance = 0.0
        all_data = []  # รวมทุก booking จาก 2 เดือน

        try:
            # ===== Step 1: Login =====
            session = requests.Session()
            login_payload = {
                "jsonrpc": "2.0",
                "params": {"db": login_db, "login": login_user, "password": login_pass}
            }
            login_resp = session.post(login_url, json=login_payload, timeout=30, verify=False)
            login_data = login_resp.json()

            if login_data.get('error'):
                _logger.warning("[VEHICLE BOOKING] Login FAILED | error=%s", login_data['error'])
                return

            _logger.info("[VEHICLE BOOKING] Login OK db=%s", login_db)

            # ===== Step 2: เรียก API 2 รอบ (เดือน N-1 และ N) =====
            # — API กรอง planned_start_date_t เป็น calendar month จึงต้องดึง 2 เดือนคลุมรอบตัด
            # — limit สูง (10000) เพื่อไม่ให้ pagination ตัดข้อมูลออก
            for q_month, q_year in [(prev_m, prev_y), (m, y)]:
                api_payload = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {"month": q_month, "year": int(q_year), "limit": 10000},
                }
                api_resp = session.post(api_url, json=api_payload, timeout=60, verify=False)
                api_data = api_resp.json()
                result = api_data.get('result', {})
                if result.get('status') != 'success':
                    _logger.warning("[VEHICLE BOOKING] API FAILED month=%s year=%s | result=%s",
                                    q_month, q_year, result)
                    continue
                data_list = result.get('data', [])
                _logger.info("[VEHICLE BOOKING] ดึงเดือน %s/%s: %d รายการ", q_month, q_year, len(data_list))
                all_data.extend(data_list)

            # ===== Step 3: กรองด้วย employee_code + ช่วงรอบตัด (planned_start_date_t) =====
            # ✅ match ด้วยรหัสพนักงาน HR — แม่นกว่าชื่อมาก (ไม่ต้องห่วง ชื่อสะกดต่าง/มีคำนำหน้า)
            # ฝั่ง Odoo 18 API ส่ง 'employee_code' จาก driver_id.employee_code
            found = False
            for item in all_data:
                api_emp_code = (item.get('employee_code') or '').strip()
                if not api_emp_code or api_emp_code != emp_code:
                    continue
                # ✅ ยึด "วันเวลาส่งจริง" (planned_end_date_t) เป็นหลักในการคิดรอบตัด
                #    (ตรงกับที่ฝ่ายบุคคลกรองในระบบ logistics)
                #    ถ้าไม่มีวันส่งจริง → fallback ใช้วันออกเดินทาง (planned_start_date_t) กันงานตกหล่น
                ref_str = item.get('planned_end_date_t') or item.get('planned_start_date_t')
                if not ref_str:
                    continue
                try:
                    # API ส่งเวลาเป็น UTC → +7 ชม. เป็นเวลาไทยก่อนเทียบรอบตัด
                    # (ให้ตรงกับที่ฝ่ายบุคคลกรองในระบบ logistics ซึ่งเป็นเวลาไทย)
                    planned_d = (_dt.strptime(ref_str, '%Y-%m-%d %H:%M:%S') + _td(hours=7)).date()
                except (ValueError, TypeError):
                    continue
                if not (cycle_start <= planned_d <= cycle_end):
                    continue
                travel_exp = item.get('travel_expenses', 0.0) or 0.0
                daily_allow = item.get('daily_allowance', 0.0) or 0.0
                total_travel_expenses += travel_exp
                total_daily_allowance += daily_allow
                found = True
                _logger.info(
                    "[VEHICLE BOOKING] MATCH! code=%s | driver_name=%s | booking=%s | date=%s | travel=%.2f | allowance=%.2f",
                    api_emp_code, item.get('driver_name', ''), item.get('name', ''),
                    planned_d, travel_exp, daily_allow,
                )

            if not found:
                _logger.info("[VEHICLE BOOKING] ไม่พบข้อมูลในรอบตัด | code='%s' driver='%s'",
                             emp_code, emp_fullname)

        except Exception as e:
            _logger.exception("[VEHICLE BOOKING] ERROR | %s", str(e))
            return

        _logger.info("[VEHICLE BOOKING] ★★★ รวม (ในรอบตัด) travel=%.2f | allowance=%.2f",
                     total_travel_expenses, total_daily_allowance)

        # ===== เซ็ตค่าลง field =====
        # ค่าเดินทาง = ค่าเที่ยวขนส่ง + ค่าเบี้ยเลี้ยงขนส่ง (ดึงจาก vehicle.booking odoo18 ทั้งคู่)
        # ❗ ไม่แตะ income_allowance (เบี้ยเลี้ยง) — ปล่อยให้ HR hook (payroll_allowance.py)
        #    ดึงจาก hr.manual.time.log (reason_type='ค่าเบี้ยเลี้ยงออกนอกสถานที่') เหมือนเดิม
        self.income_transport_trip = total_travel_expenses          # ค่าเที่ยวขนส่ง
        self.income_transport_allowance = total_daily_allowance      # ค่าเบี้ยเลี้ยงขนส่ง
        self.income_transport = total_travel_expenses + total_daily_allowance   # ค่าเดินทาง (รวม)

        _logger.info("[VEHICLE BOOKING] ✅ ค่าเดินทาง=%.2f (ค่าเที่ยวขนส่ง=%.2f + ค่าเบี้ยเลี้ยงขนส่ง=%.2f)",
                     self.income_transport, self.income_transport_trip, self.income_transport_allowance)

    def _get_commission_period(self):
        """ค่าคอมจ่ายเดือนถัดไป → payroll เดือน N ใช้ค่าคอมของ "เดือนก่อนหน้า" (N-1)
        คืน (month:int, year:str) ของเดือนก่อนหน้า (เดือน 1 → ธันวาคม ปีก่อน)"""
        try:
            cur_m = int(self.month)
            cur_y = int(str(self.year).strip())
        except (TypeError, ValueError):
            return self.month, str(self.year).strip()
        if cur_m == 1:
            return 12, str(cur_y - 1)
        return cur_m - 1, str(cur_y)

    def _bankheaw_active(self, month, year):
        """bankheaw (NPD_S_Group_New_V2) — สถานะการใช้งาน
        ✅ ปิดการใช้งานทั้งหมดได้ที่ System Parameter npd.commission.bankheaw_enabled
           (default '0' = ปิด) → ทุก popup/calc จะข้าม bankheaw (ไม่ดึง/ไม่แสดงแถว)
        ถ้าเปิด ('1'/'true') → ใช้เฉพาะงวด <= npd.commission.bankheaw_until
           (รูปแบบ 'YYYY-MM', default 2026-05)
        """
        Param = self.env['ir.config_parameter'].sudo()
        enabled = (Param.get_param('npd.commission.bankheaw_enabled', default='0') or '0').strip().lower()
        if enabled in ('0', 'false', 'no', 'off', ''):
            return False
        param = Param.get_param(
            'npd.commission.bankheaw_until', default='2026-05')
        try:
            ly, lm = param.split('-')
            last = (int(ly), int(lm))
        except Exception:
            last = (2026, 5)
        try:
            return (int(year), int(month)) <= last
        except (TypeError, ValueError):
            return True

    def _bankheaw_name_match(self, salesperson_name):
        """match รายการ bankheaw (NPD_S_Group_New_V2) กับพนักงานคนนี้ ด้วย "ชื่อ-นามสกุล"
        (ไม่อิง employee_code เพราะรหัสในข้อมูลบ้านเขียวไม่น่าเชื่อถือ — บางคนผิด/พิมพ์รหัสไม่ตรง)
        salesperson_name รูปแบบ "รหัส - ชื่อ นามสกุล" → ตัดรหัสนำหน้าออกแล้วเทียบชื่อ"""
        name = (salesperson_name or '').strip()
        if ' - ' in name:
            name = name.split(' - ', 1)[1].strip()
        fn = (self.firstname or '').strip()
        ln = (self.lastname or '').strip()
        if fn and ln:
            return fn in name and ln in name
        if fn:
            return fn in name
        if ln:
            return ln in name
        return False

    def _fetch_commission_sales_data(self):
        """
        ดึงค่าคอมมิชชั่น Sales จาก DB ปลายทางผ่าน psycopg2 (cross_db.commission.query)
        DB list ดูที่ System Parameter 'npd.commission.cross_db_list'
        (default: NPD_Intertrading_New, NPD_S_Group_New_V2, NPD_Bangkok_New)
        กรองจาก ชื่อ-นามสกุล, สาขา, เดือน/ปี
        รวม net_rental ทั้ง 3 db → เซ็ตลง income_commission_sale
        เรียกอัตโนมัติเมื่อเลือกพนักงาน/เปลี่ยนเดือน/ปี
        """
        self.ensure_one()

        # ✅ ติ๊ก "ปรับแก้ด้วยมือ" (ฝั่งรายได้) → ยึดค่าที่กรอกเอง ไม่ดึง API มาทับ
        if self.manual_override_income:
            _logger.info("[COMMISSION SALES] manual_override_income=True → ข้ามการดึง API ใช้ค่าที่กรอกเอง")
            return

        if not self.employee_id or not self.month or not self.year:
            return

        # ชื่อ-นามสกุลของพนักงาน (ใช้ log เฉย ๆ)
        emp_firstname = (self.firstname or '').strip()
        emp_lastname = (self.lastname or '').strip()
        emp_fullname = (emp_firstname + ' ' + emp_lastname).strip()
        # ✅ จับคู่ด้วย "รหัสพนักงาน" แทนชื่อ — npderp.com เก็บ employee_code ที่ res.users
        emp_code = (self.employee_id.employee_code or '').strip()
        # ชื่อสาขา
        emp_branch_name = (self.branch_id.name or '').strip()
        # เดือน/ปี — ใช้ "เดือนก่อนหน้า" (payroll เดือนนี้ จ่ายค่าคอมของเดือนที่แล้ว)
        month, year = self._get_commission_period()

        _logger.info("=" * 60)
        _logger.info("[COMMISSION SALES] เริ่มดึงค่าคอม Sales สำหรับ: %s (รหัส %s) | สาขา: %s | เดือน: %s/%s",
                     emp_fullname, emp_code, emp_branch_name, month, year)

        if not emp_code:
            _logger.warning("[COMMISSION SALES] พนักงาน %s ไม่มีรหัสพนักงาน → ข้ามการดึงค่าคอม Sale", emp_fullname)
            self.income_commission_sale = 0.0
            return

        # ✅ ดึงค่าคอม Sales ผ่าน psycopg2 ตรง (แทน HTTP API เดิม) — DB list ปรับผ่าน System Parameter ได้
        Helper = self.env['cross_db.commission.query']
        db_list = Helper.get_db_list()
        year_int = int(year)
        month_int = int(month)
        last_day = calendar.monthrange(year_int, month_int)[1]
        date_from = date(year_int, month_int, 1)
        date_to = date(year_int, month_int, last_day)

        total_commission = 0.0
        for db_name in db_list:
            rows, err = Helper.query_sales(db_name, date_from, date_to)
            if err:
                _logger.warning("[COMMISSION SALES] db=%s | %s", db_name, err)
                continue
            _logger.info("[COMMISSION SALES] db=%s | ดึงได้ %d รายการ", db_name, len(rows))
            db_net_rental = 0.0
            found = False
            for item in rows:
                api_emp_code = (item.get('employee_code') or '').strip()
                # ✅ จับคู่ด้วยรหัสพนักงาน (ไม่กรองสาขา เพราะ Sales ขายได้หลายสาขา)
                if api_emp_code == emp_code:
                    net_rental = item.get('net_rental') or 0.0
                    db_net_rental += net_rental
                    found = True
                    _logger.info(
                        "[COMMISSION SALES] MATCH! db=%s | code=%s | sales=%s | branch=%s | net_rental=%.2f",
                        db_name, api_emp_code,
                        (item.get('sales_contact_name') or '').strip(),
                        (item.get('branch_name') or '').strip(), net_rental,
                    )
            if not found:
                _logger.info("[COMMISSION SALES] ไม่พบข้อมูลที่ตรงกัน db=%s | ค้นหารหัส: %s",
                             db_name, emp_code)
            _logger.info("[COMMISSION SALES] ★ db=%s | net_rental รวม = %.2f", db_name, db_net_rental)
            total_commission += db_net_rental

        _logger.info("[COMMISSION SALES] ★★★ ยอดรวม net_rental ทั้ง %d db = %.2f",
                     len(db_list), total_commission)

        # ===== Bankheaw (เฉพาะ DB ที่มีตาราง npd_sales_commission_report, type=เซลล์, กรองชื่อ) =====
        bankheaw_db = Helper.get_bankheaw_db()
        if self._bankheaw_active(month_int, year_int):
            rows_bk, err_bk = Helper.query_bankheaw(bankheaw_db, month_int, year_int)
        else:
            rows_bk, err_bk = [], ''
            _logger.info("[COMMISSION SALES - BANKHEAW] ข้าม bankheaw งวด %s/%s (>= cutoff)", month_int, year_int)
        if err_bk:
            _logger.warning("[COMMISSION SALES - BANKHEAW] db=%s | %s", bankheaw_db, err_bk)
        else:
            for item in rows_bk:
                if item.get('sort_order', 0) != 0:
                    continue
                item_type = (item.get('type') or '').strip()
                if item_type != 'เซลล์':
                    continue
                api_sales_name = (item.get('salesperson_name') or '').strip()
                # ✅ bankheaw: match ด้วยชื่อ-นามสกุล (ไม่อิงรหัส)
                if self._bankheaw_name_match(api_sales_name):
                    net = item.get('net_total') or 0.0
                    total_commission += net
                    _logger.info("[COMMISSION SALES - BANKHEAW] MATCH (by name)! sales=%s | net_total=%.2f",
                                 api_sales_name, net)

        _logger.info("=" * 60)
        _logger.info("[COMMISSION SALES] ★★★ ยอดรวม net_rental (รวม bankheaw) = %.2f", total_commission)

        # คำนวณอัตราคอมมิชชั่นตามขั้นบันได — เลือกประเภทตามรายชื่อ Sales สำนักงานใหญ่
        # ✅ Sales สนญ.: gate ต้องเกิน 100,000 ถึงจะคิด (อยู่ใน _sales_commission_rate_amount)
        comm_type = self._get_sale_commission_type()
        rate, commission_amount = self._sales_commission_rate_amount(total_commission, comm_type)

        if comm_type == 'sale_headoffice' and total_commission <= self.SALES_HEADOFFICE_MIN:
            _logger.info("[COMMISSION SALES] ★ Sales สนญ. ยอดรวม %.2f ไม่เกิน %.0f → ค่าคอม = 0",
                         total_commission, self.SALES_HEADOFFICE_MIN)
        _logger.info("[COMMISSION SALES] ★★★ ประเภท=%s | อัตรา = %.2f%% | ค่าคอม = %.2f x %.2f%% = %.2f",
                     comm_type, rate, total_commission, rate, commission_amount)
        _logger.info("=" * 60)

        # prorate กรณีพนักงานลาออกในเดือนที่ทำเงินเดือน: (commission / 30) × วันที่ออก
        # ลาออกก่อนเดือน payroll → ไม่ให้ค่าคอม (0)
        emp = self.employee_id
        if emp.resign_date:
            try:
                # เทียบกับ "เดือนค่าคอม" (เดือนก่อน) ให้ตรงกับเดือนที่ดึงยอดมา
                cm_month, cm_year = self._get_commission_period()
                py = int(cm_year)
                pm = int(cm_month)
                rd = emp.resign_date
                if rd.year < py or (rd.year == py and rd.month < pm):
                    _logger.info("[COMMISSION SALES] ★ พนักงานลาออกก่อนเดือน %s/%s → ค่าคอม = 0", pm, py)
                    commission_amount = 0.0
                elif rd.year == py and rd.month == pm:
                    original = commission_amount
                    commission_amount = (commission_amount / 30.0) * rd.day
                    _logger.info("[COMMISSION SALES] ★ prorate ลาออก %s: %.2f / 30 × %d = %.2f",
                                 rd, original, rd.day, commission_amount)
            except (TypeError, ValueError):
                pass

        # เซ็ตค่าลง field ค่าคอมมิชชั่นSale (ยอดที่คิด % แล้ว + prorate ถ้าลาออก)
        self.income_commission_sale = commission_amount

    def _fetch_commission_branch_data(self):
        """
        ดึงค่าคอมมิชชั่นสาขา จาก DB ปลายทางผ่าน psycopg2 (cross_db.commission.query)
        DB list ดูที่ System Parameter 'npd.commission.cross_db_list'
        (default: NPD_Intertrading_New, NPD_S_Group_New_V2, NPD_Bangkok_New)
        กรองจาก ชื่อสาขา, เดือน/ปี
        รวม net_rental ทั้ง 3 db แล้ว หารด้วยจำนวนพนักงาน active ในสาขาเดียวกัน
        → เซ็ตลง income_commission
        """
        self.ensure_one()

        # ✅ ติ๊ก "ปรับแก้ด้วยมือ" (ฝั่งรายได้) → ยึดค่าที่กรอกเอง ไม่ดึง API มาทับ
        if self.manual_override_income:
            _logger.info("[COMMISSION BRANCH] manual_override_income=True → ข้ามการดึง API ใช้ค่าที่กรอกเอง")
            return

        if not self.employee_id or not self.month or not self.year:
            return

        # ชื่อสาขาจากพนักงาน
        emp_branch_name = (self.branch_id.name or '').strip()
        if not emp_branch_name:
            _logger.info("[COMMISSION BRANCH] พนักงานไม่มีสาขา ข้าม")
            return

        # ใช้ "เดือนก่อนหน้า" (payroll เดือนนี้ จ่ายค่าคอมของเดือนที่แล้ว)
        month, year = self._get_commission_period()

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

        # ✅ ดึงค่าคอมสาขา + Sales (ของสาขานี้) + bankheaw ผ่าน psycopg2 ตรง (แทน HTTP API เดิม)
        Helper = self.env['cross_db.commission.query']
        db_list = Helper.get_db_list()
        year_int = int(year)
        month_int = int(month)
        last_day = calendar.monthrange(year_int, month_int)[1]
        date_from = date(year_int, month_int, 1)
        date_to = date(year_int, month_int, last_day)

        # ===== ยอดสาขา (กรองตามชื่อสาขา) =====
        total_net_rental = 0.0
        total_sql_expense = 0.0   # SQL total_expense (vendor+advance+voucher) — ใช้เช็คเงื่อนไข > 0 ก่อนบวก salary
        for db_name in db_list:
            rows, err = Helper.query_branch(db_name, date_from, date_to)
            if err:
                _logger.warning("[COMMISSION BRANCH] db=%s | %s", db_name, err)
                continue
            _logger.info("[COMMISSION BRANCH] db=%s | ดึงได้ %d รายการ", db_name, len(rows))
            db_net_rental = 0.0
            found = False
            for item in rows:
                api_branch_name = (item.get('branch_name') or '').strip()
                if api_branch_name == emp_branch_name:
                    net_rental = item.get('net_rental') or 0.0
                    db_net_rental += net_rental
                    total_sql_expense += item.get('total_expense') or 0.0
                    found = True
                    _logger.info("[COMMISSION BRANCH] MATCH! db=%s | branch=%s | net_rental=%.2f",
                                 db_name, api_branch_name, net_rental)
            if not found:
                _logger.info("[COMMISSION BRANCH] ไม่พบสาขาที่ตรงกัน db=%s | ค้นหา: %s",
                             db_name, emp_branch_name)
            _logger.info("[COMMISSION BRANCH] ★ db=%s | net_rental รวม = %.2f", db_name, db_net_rental)
            total_net_rental += db_net_rental

        _logger.info("[COMMISSION BRANCH] ★ net_rental สาขา รวมทั้ง %d db = %.2f",
                     len(db_list), total_net_rental)

        # ===== ยอด Sales (กรองตามสาขาเดียวกัน) =====
        sales_total_net_rental = 0.0
        for db_name in db_list:
            rows, err = Helper.query_sales(db_name, date_from, date_to)
            if err:
                continue
            for item in rows:
                api_branch = (item.get('branch_name') or '').strip()
                if api_branch == emp_branch_name:
                    sales_total_net_rental += item.get('net_rental') or 0.0

        _logger.info("[COMMISSION BRANCH] ★ net_rental Sales (สาขา %s) รวมทั้ง %d db = %.2f",
                     emp_branch_name, len(db_list), sales_total_net_rental)

        # ===== Bankheaw (สาขา + เซลล์ ของสาขานี้) =====
        bankheaw_db = Helper.get_bankheaw_db()
        bankheaw_branch_net = 0.0
        bankheaw_sales_net = 0.0
        if self._bankheaw_active(month_int, year_int):
            rows_bk, err_bk = Helper.query_bankheaw(bankheaw_db, month_int, year_int)
        else:
            rows_bk, err_bk = [], ''
            _logger.info("[COMMISSION BRANCH - BANKHEAW] ข้าม bankheaw งวด %s/%s (>= cutoff)", month_int, year_int)
        if err_bk:
            _logger.warning("[COMMISSION BRANCH - BANKHEAW] db=%s | %s", bankheaw_db, err_bk)
        else:
            for item in rows_bk:
                if item.get('sort_order', 0) != 0:
                    continue
                api_branch = (item.get('branch_name') or '').strip()
                if api_branch != emp_branch_name:
                    continue
                item_type = (item.get('type') or '').strip()
                net = item.get('net_total') or 0.0
                if item_type == 'สาขา':
                    bankheaw_branch_net += net
                elif item_type == 'เซลล์':
                    bankheaw_sales_net += net

        _logger.info("[COMMISSION BRANCH] ★ bankheaw สาขา = %.2f | bankheaw เซลล์ = %.2f",
                     bankheaw_branch_net, bankheaw_sales_net)

        total_net_rental += bankheaw_branch_net
        sales_total_net_rental += bankheaw_sales_net

        _logger.info("[COMMISSION BRANCH] ★ net_rental สาขา (รวม bankheaw) = %.2f", total_net_rental)
        _logger.info("[COMMISSION BRANCH] ★ net_rental Sales (รวม bankheaw) = %.2f", sales_total_net_rental)

        # ===== JV + salary รวมอยู่ใน net_rental ต่อ DB แล้ว (SQL_BRANCH) — ไม่ต้องหักซ้ำ =====
        # SQL_BRANCH คำนวณ total_expense = vendor+advance+voucher+JV+salary (จาก snapshot
        # ต่อ DB ที่กรอง company แล้ว) ตรงกับ _compute_branch_data ของรายงานเป๊ะ
        _logger.info("[COMMISSION BRANCH] ★ net_rental สาขา (รวม JV+salary ใน SQL_BRANCH แล้ว) = %.2f",
                     total_net_rental)

        # ===== ดึงอัตราค่าคอมจากตั้งค่า =====
        rate_model = self.env['commission.rate.branch.sales']
        branch_rate, sales_rate = rate_model.get_rates()

        # ===== คำนวณ: คิดอัตราก่อนรวม =====
        # ✅ ค่าคอม "สาขา" คิดเฉพาะเมื่อ รวมยอดสุทธิสาขา (total_net_rental) > 100,000
        #    ถ้าไม่เกิน → ค่าคอมสาขา = 0 (ส่วน Sales คิดตามปกติ ไม่เกี่ยวกับเงื่อนไขนี้)
        BRANCH_COMMISSION_MIN = 100000.0
        if total_net_rental > BRANCH_COMMISSION_MIN:
            branch_after_rate = total_net_rental * (branch_rate / 100.0)
        else:
            branch_after_rate = 0.0
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

        # prorate กรณีพนักงานลาออกในเดือนที่ทำเงินเดือน: (commission / 30) × วันที่ออก
        # ลาออกก่อนเดือน payroll → ไม่ให้ค่าคอม (0)
        emp = self.employee_id
        if emp.resign_date:
            try:
                # เทียบกับ "เดือนค่าคอม" (เดือนก่อน) ให้ตรงกับเดือนที่ดึงยอดมา
                cm_month, cm_year = self._get_commission_period()
                py = int(cm_year)
                pm = int(cm_month)
                rd = emp.resign_date
                if rd.year < py or (rd.year == py and rd.month < pm):
                    _logger.info("[COMMISSION BRANCH] ★ พนักงานลาออกก่อนเดือน %s/%s → ค่าคอม = 0", pm, py)
                    commission_per_person = 0.0
                elif rd.year == py and rd.month == pm:
                    original = commission_per_person
                    commission_per_person = (commission_per_person / 30.0) * rd.day
                    _logger.info("[COMMISSION BRANCH] ★ prorate ลาออก %s: %.2f / 30 × %d = %.2f",
                                 rd, original, rd.day, commission_per_person)
            except (TypeError, ValueError):
                pass

        # เซ็ตค่าลง field ค่าคอมมิชชั่นสาขา (ยอดที่คิด % แล้ว + prorate ถ้าลาออก)
        self.income_commission = commission_per_person

    def action_view_commission_branch_detail(self):
        """ปุ่มดูรายละเอียดค่าคอมมิชชั่นสาขา — แสดง popup ยอดแต่ละ DB"""
        self.ensure_one()

        emp_branch_name = (self.branch_id.name or '').strip()
        # ใช้ "เดือนก่อนหน้า" ให้ตรงกับยอดค่าคอมที่คิดใน payroll
        month, year = self._get_commission_period()
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

        # ✅ ดึงผ่าน psycopg2 ตรง (แทน HTTP API เดิม) — DB list ปรับผ่าน System Parameter ได้
        Helper = self.env['cross_db.commission.query']
        db_list = Helper.get_db_list()
        year_int = int(year)
        month_int = int(month)
        last_day = calendar.monthrange(year_int, month_int)[1]
        date_from = date(year_int, month_int, 1)
        date_to = date(year_int, month_int, last_day)

        # ===== ยอดต่อ DB — query_branch net_rental รวม JV + salary มาแล้วในตัว =====
        # (SQL_BRANCH คำนวณ total_expense = vendor+advance+voucher+JV+salary เหมือนรายงาน)
        lines = []
        total_net_rental = 0.0
        for db_name in db_list:
            entry_net = 0.0
            match_count = 0
            rows, err = Helper.query_branch(db_name, date_from, date_to)
            if err:
                status = 'Error: %s' % err[:60]
            else:
                for item in rows:
                    if (item.get('branch_name') or '').strip() == emp_branch_name:
                        entry_net += item.get('net_rental') or 0.0
                        match_count += 1
                status = 'สำเร็จ' if match_count > 0 else 'ไม่พบข้อมูลที่ตรงกัน'
            lines.append((0, 0, {
                'db_name': db_name,
                'status': status,
                'match_count': match_count,
                'net_rental': entry_net,
            }))
            total_net_rental += entry_net

        # ===== ยอด Sales (กรองตามสาขาเดียวกัน) =====
        sales_lines = []
        sales_total_net_rental = 0.0
        for db_name in db_list:
            rows, err = Helper.query_sales(db_name, date_from, date_to)
            if err:
                _logger.warning("[COMMISSION BRANCH DETAIL - SALES] db=%s | %s", db_name, err)
                continue
            for item in rows:
                api_branch = (item.get('branch_name') or '').strip()
                if api_branch == emp_branch_name:
                    net_rental_sales = item.get('net_rental') or 0.0
                    sales_total_net_rental += net_rental_sales
                    sales_lines.append((0, 0, {
                        'db_name': db_name,
                        'sales_contact_name': item.get('sales_contact_name') or '',
                        'branch_name': api_branch,
                        'rental_amount': item.get('rental_amount') or 0.0,
                        'payment_received': item.get('payment_received') or 0.0,
                        'outstanding_debt': item.get('outstanding_debt') or 0.0,
                        'shipping_cost': item.get('shipping_cost') or 0.0,
                        'net_rental': net_rental_sales,
                    }))

        # ===== Bankheaw (สาขา → detail_lines, เซลล์ → sales_lines) =====
        bankheaw_db = Helper.get_bankheaw_db()
        if self._bankheaw_active(month_int, year_int):
            rows_bk, err_bk = Helper.query_bankheaw(bankheaw_db, month_int, year_int)
        else:
            rows_bk, err_bk = [], ''
            _logger.info("[COMMISSION BRANCH DETAIL - BANKHEAW] ข้าม bankheaw งวด %s/%s (>= cutoff)", month_int, year_int)
        if err_bk:
            _logger.warning("[COMMISSION BRANCH DETAIL - BANKHEAW] db=%s | %s", bankheaw_db, err_bk)
        else:
            for item in rows_bk:
                if item.get('sort_order', 0) != 0:
                    continue
                api_branch = (item.get('branch_name') or '').strip()
                if api_branch != emp_branch_name:
                    continue
                item_type = (item.get('type') or '').strip()
                net = item.get('net_total') or 0.0
                if item_type == 'สาขา':
                    lines.append((0, 0, {
                        'db_name': bankheaw_db + ' (bankheaw)',
                        'status': 'สำเร็จ',
                        'match_count': 1,
                        'net_rental': net,
                    }))
                    total_net_rental += net
                elif item_type == 'เซลล์':
                    sales_lines.append((0, 0, {
                        'db_name': bankheaw_db + ' (bankheaw)',
                        'sales_contact_name': item.get('salesperson_name') or '',
                        'branch_name': api_branch,
                        'rental_amount': item.get('total_rent_revenue') or 0.0,
                        'payment_received': item.get('total_paid') or 0.0,
                        'outstanding_debt': item.get('net_outstanding') or 0.0,
                        'shipping_cost': 0.0,
                        'net_rental': net,
                    }))
                    sales_total_net_rental += net

        # ===== ดึงอัตราค่าคอมจากตั้งค่า =====
        rate_model = self.env['commission.rate.branch.sales']
        branch_rate, sales_rate = rate_model.get_rates()

        # ===== คำนวณ: คิดอัตราก่อนรวม =====
        # ✅ ค่าคอม "สาขา" คิดเฉพาะเมื่อ รวมยอดสุทธิสาขา > 100,000 (ไม่เกิน = 0) — ตรงกับตอนคิดจริง
        if total_net_rental > 100000.0:
            branch_after_rate = total_net_rental * (branch_rate / 100.0)
        else:
            branch_after_rate = 0.0
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
        # ✅ จับคู่ด้วยรหัสพนักงาน ให้ตรงกับ _fetch_commission_sales_data
        emp_code = (self.employee_id.employee_code or '').strip()
        emp_branch_name = (self.branch_id.name or '').strip()
        # ประเภทค่าคอม Sale ตามรายชื่อ Sales สำนักงานใหญ่
        comm_type = self._get_sale_commission_type()
        # ใช้ "เดือนก่อนหน้า" ให้ตรงกับยอดค่าคอมที่คิดใน payroll
        month, year = self._get_commission_period()

        # ✅ ดึงผ่าน psycopg2 ตรง (แทน HTTP API เดิม) — DB list ปรับผ่าน System Parameter ได้
        Helper = self.env['cross_db.commission.query']
        db_list = Helper.get_db_list()
        year_int = int(year)
        month_int = int(month)
        last_day = calendar.monthrange(year_int, month_int)[1]
        date_from = date(year_int, month_int, 1)
        date_to = date(year_int, month_int, last_day)

        lines = []
        total_commission = 0.0
        for db_name in db_list:
            line_vals = {'db_name': db_name, 'status': '', 'match_count': 0, 'net_rental': 0.0}
            rows, err = Helper.query_sales(db_name, date_from, date_to)
            if err:
                line_vals['status'] = 'Error: %s' % err[:60]
                lines.append((0, 0, line_vals))
                continue
            db_net_rental = 0.0
            match_count = 0
            for item in rows:
                api_emp_code = (item.get('employee_code') or '').strip()
                if emp_code and api_emp_code == emp_code:
                    db_net_rental += item.get('net_rental') or 0.0
                    match_count += 1
            line_vals['net_rental'] = db_net_rental
            line_vals['match_count'] = match_count
            line_vals['status'] = 'สำเร็จ' if match_count > 0 else 'ไม่พบข้อมูลที่ตรงกัน'
            total_commission += db_net_rental
            lines.append((0, 0, line_vals))

        # ===== Bankheaw (type=เซลล์, match ด้วยชื่อ-นามสกุล) =====
        # ตั้งแต่งวด 6/2026 เป็นต้นไป → ข้าม bankheaw ไปเลย (ไม่ดึง/ไม่แสดงแถวนี้)
        if self._bankheaw_active(month_int, year_int):
            bankheaw_db = Helper.get_bankheaw_db()
            bk_line_vals = {'db_name': bankheaw_db + ' (bankheaw)', 'status': '', 'match_count': 0, 'net_rental': 0.0}
            rows_bk, err_bk = Helper.query_bankheaw(bankheaw_db, month_int, year_int)
            if err_bk:
                bk_line_vals['status'] = 'Error: %s' % err_bk[:60]
            else:
                bk_net = 0.0
                bk_count = 0
                for item in rows_bk:
                    if item.get('sort_order', 0) != 0:
                        continue
                    item_type = (item.get('type') or '').strip()
                    if item_type != 'เซลล์':
                        continue
                    # ✅ bankheaw: match ด้วยชื่อ-นามสกุล (ไม่อิงรหัส)
                    api_sales_name = (item.get('salesperson_name') or '').strip()
                    if self._bankheaw_name_match(api_sales_name):
                        bk_net += item.get('net_total') or 0.0
                        bk_count += 1
                bk_line_vals['net_rental'] = bk_net
                bk_line_vals['match_count'] = bk_count
                bk_line_vals['status'] = 'สำเร็จ' if bk_count > 0 else 'ไม่พบข้อมูลที่ตรงกัน'
                total_commission += bk_net
            lines.append((0, 0, bk_line_vals))

        # ✅ คิด rate/amount ผ่าน helper เดียวกับ calc (รวม gate Sales สนญ. > 100,000)
        s_rate, s_amount = self._sales_commission_rate_amount(total_commission, comm_type)

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
            # ✅ Sales สนญ.: gate ต้องเกิน 100,000 (helper เดียวกับ calc → ตรงกันเสมอ)
            'commission_rate': s_rate,
            'commission_result': s_amount,
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
        # ✅ ล็อก: ห้ามลบรายการเงินเดือนที่ "เลยวันที่จ่ายเงิน" แล้ว (กันลบข้อมูลที่จ่ายไปแล้ว)
        #    ยกเว้นเรียกผ่าน context force_unlink_paid=True (ใช้ใน auto-cleanup ของระบบ)
        if not self.env.context.get('force_unlink_paid'):
            today = fields.Date.today()
            for record in self:
                if record.payment_date and today > record.payment_date:
                    raise UserError(
                        "ไม่สามารถลบรายการเงินเดือนของ %s (%s) ได้ "
                        "เนื่องจากเลยวันที่จ่ายเงิน (%s) แล้ว"
                        % (record.firstname or (record.employee_id.firstname if record.employee_id else '') or '',
                           record.employee_code or '',
                           record.payment_date.strftime('%d/%m/%Y')))
        for record in self:
            data = {'odoo_id': record.id}
            self._send_data_to_php_api('delete', data)
        return super(PayrollSalary, self).unlink()

    @api.depends('year')
    def _compute_holiday_template(self):
        for rec in self:
            rec.holiday_template_year = rec.year

    # รหัสพนักงานระดับประธาน — ข้ามการคำนวณ OT + ขาดลามาสาย
    EXECUTIVE_EMPLOYEE_CODES = ('0022', '1343', '0203')

    # บุคคลพิเศษ — ล็อกภาษีต่อเดือนคงที่ + กำหนดว่าคิด ปกส. ไหม
    #   tax_monthly=ตัวเลข → ล็อกภาษีคงที่, tax_monthly=None → คิดภาษีตามปกติ
    #   skip_sso=True  → ไม่หักประกันสังคม (sso = 0)
    #   skip_sso=False → คิด ปกส. ตามปกติ
    # ⚠️ เลิกล็อกภาษีคงที่แล้ว — บุคคลพิเศษคิดภาษีตามสูตรปกติเหมือนพนักงานทั่วไป
    #    ถ้าเดือนไหนต้องการล็อกยอดเอง ให้ติ๊ก "ปรับแก้ด้วยมือ (แก้ภาษี/เดือนเอง)"
    #    ที่แท็บการตั้งค่าภาษีของเดือนนั้นแทน (ชนะทุกอย่าง)
    EXECUTIVE_TAX_CONFIG = {
        '0022': {'tax_monthly': None, 'skip_sso': True},   # ธีระพล รอดสาตร์
        '1343': {'tax_monthly': None, 'skip_sso': True},   # ฐนันท์พัสร์ ฤทธาภรณ์
        '0203': {'tax_monthly': None, 'skip_sso': False},  # จิดาภา รอดสาตร์ (ปกส. ปกติ)
        # 0539 สุดคนึง รอดสาตร์ — เอาออกจากบุคคลพิเศษ คิดภาษี + ปกส. ตามปกติ
    }

    def _prepare_ot_lines(self):
        self.ensure_one()

        # ✅ ข้ามคำนวณ OT สำหรับประธาน
        if self.employee_code and self.employee_code in self.EXECUTIVE_EMPLOYEE_CODES:
            _logger.info("[OT] ข้ามคำนวณ OT สำหรับประธาน emp=%s", self.employee_code)
            return [], 0.0, None

        # ----- ค่าพื้นฐานที่ใช้ทั้ง PHP API และ hr.manual.time.log -----
        ot_lines_to_create = []
        total_ot_amount = 0.0
        warning_dict = None

        # ✅ ดึงตารางกะทำงานของพนักงาน
        work_schedule = self.env['hr.work.schedule'].search(
            [('employee_id', '=', self.employee_id.id)], limit=1) if self.employee_id else False

        # ✅ ดึงวันหยุดนักขัตฤกษ์ของปี (payroll.holiday.year เป็น Integer แต่ self.year เป็น Char → แปลงก่อน)
        try:
            year_int = int(self.year)
        except (TypeError, ValueError):
            year_int = 0
        holiday_template = self.env['payroll.holiday'].search([('year', '=', year_int)], limit=1)
        holidays = [line.date.strftime('%Y-%m-%d') for line in holiday_template.line_ids] if holiday_template else []
        _logger.info("[OT] Holiday template year=%s found=%s holidays_count=%d",
                     year_int, bool(holiday_template), len(holidays))

        # ✅ เงินเดือนต่อชั่วโมง
        salary_per_day = (self.base_salary or 0.0) / 30
        hourly_rate_raw = salary_per_day / 8.0
        hourly_rate = round_half_up(hourly_rate_raw)

        # ----- ดึง OT จาก PHP API (เฉพาะ weekday/sunday — holiday จะมาจาก manual log) -----
        ot_logs = []
        if self.ot_api_url and self.employee_code:
            # ✅ ส่ง cutoff_day ไปด้วย เพื่อให้ API ใช้รอบเงินเดือน 25–24 (ไม่ใช่เดือนปฏิทิน)
            params = {'employee_code': self.employee_code, 'month': self.month, 'year': self.year,
                      'cutoff_day': self.cutoff_day or 24}
            _logger.info("OT API Request URL: %s", self.ot_api_url)
            _logger.info("OT API Payload (params): %s", json.dumps(params, indent=2, ensure_ascii=False))
            try:
                response = requests.get(self.ot_api_url, params=params, timeout=10)
                response.raise_for_status()
                ot_logs = response.json() or []
                _logger.info("OT API Response: %s", json.dumps(ot_logs, indent=2, ensure_ascii=False))
            except requests.exceptions.MissingSchema:
                warning_dict = {
                    'warning': {'title': _("API URL Error"),
                                'message': _("รูปแบบ API URL ไม่ถูกต้อง กรุณาขึ้นต้นด้วย http:// หรือ https://")}
                }
                ot_logs = []
            except requests.exceptions.RequestException as e:
                warning_dict = {
                    'warning': {'title': _("API Connection Error"),
                                'message': _("ไม่สามารถเชื่อมต่อ API ได้: %s") % e}
                }
                ot_logs = []

        for log in ot_logs:
            # ดึงวันที่จาก log['work_date']
            work_date = fields.Date.from_string(log['work_date'])

            # ⚠️ ข้ามวันหยุดนักขัตฤกษ์ — จะดึงจาก hr.manual.time.log แทน (ดูบล็อกด้านล่าง)
            if work_date.strftime('%Y-%m-%d') in holidays:
                continue

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

            # ไม่ใช่วันหยุดนักขัตฤกษ์ → จัดเป็น weekday หรือ sunday
            if self._is_outside_shift(work_date, start_dt, end_dt, work_schedule):
                ot_type = 'weekday'
                multiplier = 1.5

                # ✅ ตัดเวลาที่อยู่ในกะออก
                shift_start, shift_end = self._get_shift_time(work_date, work_schedule)
                ot_hours = self._calculate_ot_outside_shift(start_dt, end_dt, shift_start, shift_end)
            else:
                ot_type = 'sunday'
                multiplier = 1.0

                # ✅ หักเวลาพักเที่ยง 12:00–13:00 ออก
                lunch_start = datetime.datetime.combine(start_dt.date(), datetime.time(12, 0))
                lunch_end = datetime.datetime.combine(start_dt.date(), datetime.time(13, 0))
                overlap_start = max(start_dt, lunch_start)
                overlap_end = min(end_dt, lunch_end)
                if overlap_start < overlap_end:
                    ot_hours -= (overlap_end - overlap_start).total_seconds() / 3600.0
                ot_hours = max(0, ot_hours)

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

        # ✅ ดึง OT วันหยุดนักขัตฤกษ์จาก hr.manual.time.log (reason_type='ทำงานวันหยุด', state='อนุมัติ')
        # ใช้ work_date / checkin_time / checkout_time × อัตราเงินเดือนต่อชั่วโมง × 2.0
        # เช็ค hr.manual.time.log model ผ่าน try/except (กรณี hr_attendance_branch ยังไม่ load)
        ManualTimeLogModel = None
        try:
            ManualTimeLogModel = self.env['hr.manual.time.log']
        except KeyError:
            pass
        if self.employee_id and self.month and self.year and ManualTimeLogModel is not None:
            try:
                m = int(self.month)
                y = int(self.year)
                end_day = self.cutoff_day or 24
                start_day = (self.period_id.cutoff_start_day if self.period_id else None) or 25
                last_end = calendar.monthrange(y, m)[1]
                end_date_cycle = date(y, m, min(end_day, last_end))
                if m == 1:
                    prev_m, prev_y = 12, y - 1
                else:
                    prev_m, prev_y = m - 1, y
                last_start = calendar.monthrange(prev_y, prev_m)[1]
                start_date_cycle = date(prev_y, prev_m, min(start_day, last_start))

                manual_logs = ManualTimeLogModel.search([
                    ('employee_id', '=', self.employee_id.id),
                    ('reason_type', '=', 'ทำงานวันหยุด'),
                    ('state', '=', 'อนุมัติ'),
                    ('work_date', '>=', start_date_cycle),
                    ('work_date', '<=', end_date_cycle),
                ])
                # วันที่ที่มี OT จาก PHP API แล้ว (กันนับซ้ำกับบล็อกด้านบน)
                php_ot_dates = {cmd[2]['date'] for cmd in ot_lines_to_create}
                for ml in manual_logs:
                    if not ml.work_date or not ml.checkin_time or not ml.checkout_time:
                        continue
                    # ✅ ประเภทการเพิ่มเวลา 'ทำงานวันหยุด' (อนุมัติแล้ว) → ได้ OT 2 เท่าเสมอ
                    #    ไม่จำกัดเฉพาะวันหยุดนักขัตฤกษ์ (payroll.holiday) อีกต่อไป
                    #    ครอบคลุมวันหยุดประจำสัปดาห์ (เสาร์/อาทิตย์) ที่ขออนุมัติทำงานวันหยุดด้วย
                    # กันนับซ้ำ: ถ้าวันนั้นมี OT จาก PHP API แล้ว ให้ข้าม
                    if ml.work_date in php_ot_dates:
                        continue
                    try:
                        start_dt = datetime.datetime.strptime(
                            f"{ml.work_date} {ml.checkin_time}", "%Y-%m-%d %H:%M:%S")
                        end_dt = datetime.datetime.strptime(
                            f"{ml.work_date} {ml.checkout_time}", "%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        continue
                    if end_dt <= start_dt:
                        end_dt += datetime.timedelta(days=1)
                    ot_hours = (end_dt - start_dt).total_seconds() / 3600.0

                    # หักเวลาพักเที่ยง 12:00–13:00 ออก
                    lunch_start = datetime.datetime.combine(start_dt.date(), datetime.time(12, 0))
                    lunch_end = datetime.datetime.combine(start_dt.date(), datetime.time(13, 0))
                    overlap_start = max(start_dt, lunch_start)
                    overlap_end = min(end_dt, lunch_end)
                    if overlap_start < overlap_end:
                        ot_hours -= (overlap_end - overlap_start).total_seconds() / 3600.0
                    ot_hours = max(0, ot_hours)

                    ot_amount = ot_hours * hourly_rate * 2.0
                    total_ot_amount += ot_amount
                    ot_lines_to_create.append((0, 0, {
                        'date': ml.work_date,
                        'start_time': start_dt,
                        'end_time': end_dt,
                        'start_time_x': ml.checkin_time,
                        'end_time_x': ml.checkout_time,
                        'ot_hours': ot_hours,
                        'ot_amount': ot_amount,
                        'ot_type': 'holiday',
                    }))
            except (ValueError, TypeError) as e:
                _logger.warning("[OT HOLIDAY] เกิดข้อผิดพลาดตอนคำนวณรอบ: %s", e)

        return ot_lines_to_create, total_ot_amount, warning_dict

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

    THAI_DOW_NAMES = {0: 'จันทร์', 1: 'อังคาร', 2: 'พุธ', 3: 'พฤหัสบดี',
                      4: 'ศุกร์', 5: 'เสาร์', 6: 'อาทิตย์'}

    def _format_missed_days_detail(self, date_strs):
        """แปลง list วันที่ ['2026-05-09', ...] เป็น text แสดงในฟอร์ม"""
        if not date_strs:
            return ''
        lines = ['สาเหตุ: ไม่มีเช็คอิน/เช็คเอาท์ และไม่มีใบลาที่อนุมัติในวันต่อไปนี้']
        for d in date_strs:
            try:
                dt = datetime.datetime.strptime(d, '%Y-%m-%d').date()
                dow = self.THAI_DOW_NAMES.get(dt.weekday(), '')
                lines.append("• %s (%s)" % (dt.strftime('%d/%m/%Y'), dow))
            except (ValueError, TypeError):
                lines.append("• %s" % d)
        return '\n'.join(lines)

    def _format_deduction_detail(self, late_log, early_log, leave_log,
                                 missed_days_log, salary_per_minute, salary_per_day):
        """แจกแจงรายการหักแต่ละวันเป็นข้อความ ให้ HR ตรวจสอบ
        (เฉพาะรายการที่ "หักจริง" — ลาที่ไม่หัก เช่น ลาป่วยมีใบรับรอง/ลาได้ค่าจ้าง จะไม่ขึ้น)"""
        def _fmt_date(d):
            try:
                dt = datetime.datetime.strptime(d, '%Y-%m-%d').date()
                dow = self.THAI_DOW_NAMES.get(dt.weekday(), '')
                return "%s (%s)" % (dt.strftime('%d/%m/%Y'), dow)
            except (ValueError, TypeError):
                return str(d)

        sections = []

        # หักลา (ยอดเงินมาจาก PHP ต่อใบลา)
        if leave_log:
            lines = ['• ลา (หักจริง):']
            for it in leave_log:
                amt = round(float(it.get('deduction') or 0.0), 2)
                lines.append("   - %s | %s | หัก %.2f" % (
                    _fmt_date(it.get('date')), it.get('type') or '', amt))
            sections.append('\n'.join(lines))

        # หักสาย (นาที × ค่าจ้างต่อนาที)
        if late_log:
            lines = ['• มาสาย:']
            for it in late_log:
                mins = int(it.get('minutes') or 0)
                lines.append("   - %s | %d นาที | หัก %.2f" % (
                    _fmt_date(it.get('date')), mins, round(mins * salary_per_minute, 2)))
            sections.append('\n'.join(lines))

        # หักออกก่อนเวลา (นาที × ค่าจ้างต่อนาที)
        if early_log:
            lines = ['• ออกก่อนเวลา:']
            for it in early_log:
                mins = int(it.get('minutes') or 0)
                lines.append("   - %s | %d นาที | หัก %.2f" % (
                    _fmt_date(it.get('date')), mins, round(mins * salary_per_minute, 2)))
            sections.append('\n'.join(lines))

        # หักขาดงานเต็มวัน
        if missed_days_log:
            lines = ['• ขาดงาน (เต็มวัน):']
            for d in missed_days_log:
                lines.append("   - %s | หัก %.2f" % (_fmt_date(d), round(salary_per_day, 2)))
            sections.append('\n'.join(lines))

        return '\n'.join(sections)

    def _build_deduction_line_vals(self, late_log, early_log, leave_log,
                                   missed_days_log, salary_per_minute, salary_per_day):
        """สร้าง list ของ dict สำหรับตาราง deduction_line_ids
        (แจกแจง วันที่/วัน/ประเภท/รายละเอียด/เวลา/นาที/ยอดหัก รายบรรทัด)
        เฉพาะรายการที่หักจริงเท่านั้น"""
        def _day_name(d):
            try:
                dt = datetime.datetime.strptime(d, '%Y-%m-%d').date()
                return self.THAI_DOW_NAMES.get(dt.weekday(), '')
            except (ValueError, TypeError):
                return ''

        def _to_date(d):
            try:
                return datetime.datetime.strptime(d, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return False

        vals = []

        # ลา (ยอดหักมาจาก PHP ต่อใบลา)
        for it in (leave_log or []):
            d = it.get('date')
            t_start = it.get('start')
            t_end = it.get('end')
            time_detail = ('%s-%s' % (t_start, t_end)) if (t_start and t_end) else ''
            vals.append({
                'date': _to_date(d),
                'day_name': _day_name(d),
                'category': 'leave',
                'description': it.get('type') or 'ลา',
                'time_detail': time_detail,
                'minutes': 0.0,
                'amount': round(float(it.get('deduction') or 0.0), 2),
            })

        # มาสาย (นาที × ค่าจ้างต่อนาที)
        for it in (late_log or []):
            d = it.get('date')
            mins = int(it.get('minutes') or 0)
            ci = it.get('checkin')
            ss = it.get('shift_start')
            time_detail = ('เข้า %s (กะ %s)' % (ci, ss)) if (ci and ss) else ''
            vals.append({
                'date': _to_date(d),
                'day_name': _day_name(d),
                'category': 'late',
                'description': 'มาสาย',
                'time_detail': time_detail,
                'minutes': mins,
                'amount': round(mins * salary_per_minute, 2),
            })

        # ออกก่อนเวลา (นาที × ค่าจ้างต่อนาที)
        for it in (early_log or []):
            d = it.get('date')
            mins = int(it.get('minutes') or 0)
            co = it.get('checkout')
            se = it.get('shift_end')
            time_detail = ('ออก %s (เลิก %s)' % (co, se)) if (co and se) else ''
            vals.append({
                'date': _to_date(d),
                'day_name': _day_name(d),
                'category': 'early',
                'description': 'ออกก่อนเวลา',
                'time_detail': time_detail,
                'minutes': mins,
                'amount': round(mins * salary_per_minute, 2),
            })

        # ขาดงานเต็มวัน
        for d in (missed_days_log or []):
            vals.append({
                'date': _to_date(d),
                'day_name': _day_name(d),
                'category': 'absent',
                'description': 'ขาดงานเต็มวัน',
                'time_detail': 'ทั้งวัน',
                'minutes': 0.0,
                'amount': round(salary_per_day, 2),
            })

        return vals

    def _prepare_lateness_data(self):
        self.ensure_one()
        # ✅ ข้ามคำนวณขาดลามาสายสำหรับประธาน
        if self.employee_code and self.employee_code in self.EXECUTIVE_EMPLOYEE_CODES:
            _logger.info("[LATENESS] ข้ามคำนวณขาดลามาสายสำหรับประธาน emp=%s", self.employee_code)
            return 0, 0, 0, 0, 0, 0, 0, 0, 0, [], [], [], [], None
        if not self.lateness_api_url or not self.employee_id:
            # คืนค่า 11 ตัวให้ครบรูปแบบ
            return 0, 0, 0, 0, 0, 0, 0, 0, 0, [], [], [], [], None

        work_schedule = self.env['hr.work.schedule'].search([('employee_id', '=', self.employee_id.id)], limit=1)
        if not work_schedule:
            _logger.warning("ไม่พบข้อมูลตารางการทำงานสำหรับพนักงานนี้: %s", self.employee_id.firstname)
            return 0, 0, 0, 0, 0, 0, 0, 0, 0, [], [], [], [], {
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

        # payroll.holiday.year เป็น Integer แต่ self.year เป็น Char → แปลงก่อนค้นหา
        try:
            year_int = int(self.year)
        except (TypeError, ValueError):
            year_int = 0
        current_year_holiday_template = self.env['payroll.holiday'].search([('year', '=', year_int)], limit=1)
        official_holidays = [line.date.strftime('%Y-%m-%d') for line in
                             current_year_holiday_template.line_ids] if current_year_holiday_template else []
        _logger.info("[LATENESS] Holiday template year=%s found=%s holidays_count=%d holidays=%s",
                     year_int, bool(current_year_holiday_template), len(official_holidays), official_holidays)

        # ✅ ส่ง resign_date ไปด้วย — PHP จะได้ไม่นับวันหลังลาออกเป็นขาดงาน
        resign_date_str = (self.employee_id.resign_date.strftime('%Y-%m-%d')
                           if self.employee_id.resign_date else None)

        payload = {
            'employee_code': self.employee_id.employee_code,
            'grace_period': self.lateness_grace_period,
            'work_schedule': schedule_data,
            'month': self.month,
            'year': self.year,
            'cutoff_day': self.cutoff_day,
            'official_holidays': official_holidays,
            'resign_date': resign_date_str,
        }

        _logger.info("Lateness API Payload: %s", json.dumps(payload, indent=2, ensure_ascii=False))
        try:
            response = requests.post(self.lateness_api_url, json=payload, timeout=10)
            response.raise_for_status()
            api_response = response.json()
            _logger.info("Lateness API Response: %s", json.dumps(api_response, indent=2, ensure_ascii=False))

            if api_response.get('status') == 'success':
                debug = api_response.get('debug') or {}
                missed_days_log = debug.get('missed_days_log') or []
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
                    missed_days_log,  # 10 รายการวันที่ขาดงาน (list of 'YYYY-MM-DD')
                    debug.get('late_checkin_log') or [],   # 11 [{date, minutes}]
                    debug.get('early_checkout_log') or [],  # 12 [{date, minutes}]
                    debug.get('leave_log') or [],           # 13 [{date, type, deduction}]
                    None  # 14 warning
                )
            else:
                warning_dict = {
                    'warning': {'title': _("API Error"), 'message': api_response.get('message', "Unknown error")}
                }
                return 0, 0, 0, 0, 0, 0, 0, 0, 0, [], [], [], [], warning_dict

        except requests.exceptions.RequestException as e:
            warning_dict = {
                'warning': {'title': _("API Connection Error"), 'message': _("ไม่สามารถเชื่อมต่อ API ได้: %s") % e}
            }
            return 0, 0, 0, 0, 0, 0, 0, 0, 0, [], [], [], [], warning_dict

    def _populate_all_lines(self):
        self.ensure_one()
        # safety guard กัน recursion (เช่น compute → write → populate → compute → ...)
        if self.env.context.get('_in_populate_all_lines'):
            return
        # _skip_payroll_write_side_effects: ระหว่าง populate เซ็ต ~15 field
        # ถ้าไม่ข้าม side-effect แต่ละ field จะยิง PHP + sync employee → storm
        self = self.with_context(_in_populate_all_lines=True, _skip_payroll_write_side_effects=True)
        emp_code = self.employee_id.employee_code if self.employee_id else '-'
        _logger.info("[POPULATE_ALL_LINES] START emp=%s month=%s year=%s id=%s",
                     emp_code, self.month, self.year, self.id)
        # บังคับ recompute ทุก field ที่เกี่ยวข้องก่อน — กัน stored values stale
        self._compute_actor_content_total()
        self._compute_deposit_amounts()
        self._compute_other_income_total()
        self._compute_expense_other_total()
        self._compute_other_income_breakdowns()
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
         missed_days_log,  # รายการวันที่ขาดงาน (list of 'YYYY-MM-DD')
         late_log,   # [{date, minutes}]
         early_log,  # [{date, minutes}]
         leave_log,  # [{date, type, deduction}]
         lateness_warning_dict) = self._prepare_lateness_data()

        if not self.manual_override:
            # set lateness values
            self.late_checkin_minutes = late_checkin_minutes
            self.early_checkout_minutes = early_checkout_minutes
            self.missed_days = missed_days
            # ✅ แทนที่ของเดิมทุกครั้งที่คำนวณใหม่ — ถ้าไม่มีวันขาดงาน เคลียร์เป็น ''
            self.missed_days_detail = self._format_missed_days_detail(missed_days_log) if missed_days_log else ''
            self.lateness_minutes = total_lateness_minutes
            # หักลา: เก็บทศนิยม 2 ตำแหน่ง (ตามจริง เช่น 1 ชม. = 70.54) ไม่ปัดเต็มบาท
            self.leave_deduction_total = round(leave_deduction_total, 2)


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
                        # หักพักเที่ยง 1 ชม. ถ้ากะ >= 8 ชม. (ให้ตรงกับฝั่ง PHP calculate_lateness.php)
                        if work_hours >= 8:
                            work_hours -= 1
                        total_work_hours += work_hours
                        work_days_count += 1

            average_daily_hours = (total_work_hours / work_days_count) if work_days_count > 0 else 8.0
            hourly_rate = salary_per_day / average_daily_hours if average_daily_hours > 0 else 0.0
            salary_per_minute = hourly_rate / 60.0

            late_raw = self.late_checkin_minutes * salary_per_minute
            self.late_checkin_deduction = round_half_up(late_raw)

            self.deduction_late = self.late_checkin_deduction
            self.deduction_leave = round(self.leave_deduction_total, 2)

            # ✅ ห้ามบวก early_checkout_deduction ซ้ำอีก เพราะรวมอยู่ใน deduction_absent แล้ว
            self.lateness_deduction = (
                    self.deduction_late +
                    self.deduction_leave +
                    self.deduction_absent
            )

            # ✅ แจกแจงรายละเอียดการหัก ให้ HR ตรวจสอบได้ว่าหักอะไรบ้างแต่ละวัน
            self.deduction_detail = self._format_deduction_detail(
                late_log, early_log, leave_log, missed_days_log,
                salary_per_minute, salary_per_day)

            # ✅ ตารางแจกแจงการหัก (แทนที่ของเดิมทุกครั้งที่คำนวณใหม่)
            #    ระบุ วันที่/วัน/ประเภท/รายละเอียด/เวลา/นาที/ยอดหัก รายบรรทัด
            detail_vals = self._build_deduction_line_vals(
                late_log, early_log, leave_log, missed_days_log,
                salary_per_minute, salary_per_day)
            self.deduction_line_ids = [(5, 0, 0)] + [(0, 0, v) for v in detail_vals]

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

        # ฐานเงินเดือน — prorate ให้พนักงานลาออกกลางรอบ (ดู _get_prorated_salary_income)
        lines_to_create.append((0, 0, {
            'name': 'เงินเดือน',
            'type': 'income',
            'amount': self._get_prorated_salary_income()
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

        lines_to_create.append((0, 0, {'name': 'เบี้ยเลี้ยง นอกสถานที่', 'type': 'income', 'amount': self.income_allowance}))

        lines_to_create.append((0, 0, {'name': 'ค่าอาหาร', 'type': 'income', 'amount': self.income_food}))

        lines_to_create.append((0, 0, {'name': 'ค่าเดินทาง', 'type': 'income', 'amount': self.income_transport}))

        lines_to_create.append((0, 0, {'name': 'อินเซนทีฟ', 'type': 'income', 'amount': self.income_fuel}))

        lines_to_create.append(
                (0, 0, {'name': 'ค่าคอมมิชชั่น', 'type': 'income', 'amount': self.income_commission + self.income_commission_sale}))

        # รายได้อื่นๆ = ผลรวมทั้งหมด (manual + actor + bonus + missed + เมนูเงินได้อื่นๆ)
        # → ใช้ในสลิปเงินเดือนเป็น line เดียว ไม่ double-count กับการ breakdown
        lines_to_create.append((0, 0, {
            'name': 'รายได้อื่นๆ',
            'type': 'income',
            'amount': self.income_other or 0.0,
        }))

        # รายจ่ายใหม่

        lines_to_create.append(
                (0, 0, {'name': 'กองทุนสำรองเลี้ยงชีพ', 'type': 'deduction', 'amount': self.expense_provident}))

        lines_to_create.append(
                (0, 0, {'name': 'เบิกเงินล่วงหน้า', 'type': 'deduction', 'amount': self.expense_advance}))

        lines_to_create.append((0, 0, {'name': 'เงินกู้', 'type': 'deduction', 'amount': self.expense_loan}))

        lines_to_create.append((0, 0, {'name': 'กยศ', 'type': 'deduction', 'amount': self.expense_ksl}))

        # หักเงินอื่นๆ = expense_other (รวม manual + deposit_regular + deposit_extra)
        # → ใช้ใน slip บรรทัดเดียว ไม่ double-count กับ "เงินประกันการทำงาน" (ลบออกแล้ว)
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

        # บุคคลพิเศษ — config ล็อกภาษี + ปกส.
        exec_cfg = self.EXECUTIVE_TAX_CONFIG.get(self.employee_code or '')

        # ประกันสังคม — ปัดเศษเป็นจำนวนเต็มบาทตามกฎ สปส.
        #   (เศษสตางค์ ≥ 0.50 ปัดขึ้น, < 0.50 ปัดทิ้ง = round_half_up)
        # ✅ คิดประกันสังคมจาก "เงินเดือนที่ได้จริง" (prorate ถ้าทำงานไม่เต็มเดือน)
        #    เต็มเดือน = base_salary เต็ม | ไม่เต็มเดือน = ยอด prorate (เช่น 10,400 → 520)
        sso_base = max(self.sso_min_wage, min(self._get_prorated_salary_income(), self.sso_max_wage))
        sso_amount = float(round_half_up(sso_base * (self.sso_rate / 100.0)))
        # บุคคลพิเศษที่ skip_sso → ไม่หักประกันสังคม
        if exec_cfg and exec_cfg.get('skip_sso'):
            sso_amount = 0.0
        # ✅ ติ๊ก "ปรับแก้ด้วยมือ" หรือกรอก "ประกันสังคม (กรอกเอง)" > 0 → ยึดค่านี้ ไม่คำนวณทับ
        elif self.manual_override_sso or (self.manual_sso_amount and self.manual_sso_amount > 0):
            sso_amount = self.manual_sso_amount
            _logger.info("[SSO] override ด้วยมือ → ใช้ค่า manual_sso_amount=%.2f", sso_amount)
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

        # ภาษี — คำนวณ inline จาก base_salary + ot + bonus (ไม่พึ่ง self.tax_monthly
        # ที่อาจ stale ใน onchange/create context)
        # ใช้ค่าที่คำนวณใหม่เสมอ — ถ้า user ต้องการล็อก ให้เปิด manual_override ทั้ง record
        # ฐานภาษี = รายได้ประจำ (เงินเดือน+OT+เบี้ยเลี้ยง+คอม) ×12 + รายได้ครั้งเดียว (income_other) บวกครั้งเดียว
        # ส่ง total_ot_amount (สด) แทน self.ot_total ที่อาจ stale ระหว่าง populate
        temp_recurring, temp_one_time = self._get_tax_income_base(ot_amount=total_ot_amount)
        temp_tax, _ = self._calculate_tax(temp_recurring, sso_amount, temp_one_time)
        # ✅ ติ๊ก "ปรับแก้ด้วยมือ" → ใช้ค่าที่กรอกในช่องภาษี/เดือน ไม่คำนวณทับ
        #    ต้องเช็คก่อนบุคคลพิเศษ เพราะการติ๊กเองคือเจตนาชัดของผู้ใช้
        #    ต้องชนะค่าล็อกคงที่ใน EXECUTIVE_TAX_CONFIG
        if self.manual_override_tax:
            temp_tax = self.manual_tax_amount
            _logger.info("[TAX] manual_override_tax=True → ใช้ค่าที่กรอกเอง = %.2f", temp_tax)
        # บุคคลพิเศษ — ล็อกภาษีต่อเดือนคงที่ (เฉพาะที่กำหนด tax_monthly ไว้)
        elif exec_cfg and exec_cfg.get('tax_monthly') is not None:
            temp_tax = exec_cfg['tax_monthly']

        lines_to_create.append((0, 0, {
            'name': 'ภาษีหัก ณ ที่จ่าย',
            'type': 'deduction',
            'amount': temp_tax
        }))

        # Apply to record
        # ถ้า override_ot=True → เก็บ ot_line_ids เดิมที่ user แก้ไว้ (ไม่ regenerate)
        if not self.override_ot:
            # บน real record (มี id จริง) ลบของเก่าด้วย unlink เพื่อกัน double ตอน write
            # บน NewId / onchange context ใช้ command (5,0,0) เท่านั้น เพราะ unlink ทำลาย state
            if self.id and not isinstance(self.id, models.NewId) and self.ot_line_ids:
                self.ot_line_ids.sudo().unlink()
                self.ot_line_ids = ot_lines_commands
            else:
                self.ot_line_ids = [(5, 0, 0)] + ot_lines_commands

            # 🟢 set totals จาก ot_lines_commands โดยตรง — กัน cache issue ที่ทำให้
            # _compute_ot_totals เห็น ot_line_ids เป็น (เก่า+ใหม่) แล้ว double
            new_weekday = sum(cmd[2].get('ot_amount', 0.0) for cmd in ot_lines_commands
                              if isinstance(cmd, tuple) and len(cmd) == 3
                              and cmd[2].get('ot_type') == 'weekday')
            new_holiday = sum(cmd[2].get('ot_amount', 0.0) for cmd in ot_lines_commands
                              if isinstance(cmd, tuple) and len(cmd) == 3
                              and cmd[2].get('ot_type') == 'holiday')
            new_sunday = sum(cmd[2].get('ot_amount', 0.0) for cmd in ot_lines_commands
                             if isinstance(cmd, tuple) and len(cmd) == 3
                             and cmd[2].get('ot_type') == 'sunday')
            self.ot_total_weekday = new_weekday
            self.ot_total_holiday = new_holiday
            self.ot_total_sunday = new_sunday
            self.ot_total = new_weekday + new_holiday + new_sunday
            self.manual_ot_weekday = new_weekday
            self.manual_ot_holiday = new_holiday
            self.manual_ot_sunday = new_sunday
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

    @api.depends('employee_id', 'payment_date', 'month', 'year', 'cutoff_day', 'period_id',
                 'actor_content_total',
                 'income_bonus', 'bonus_active', 'income_missed_payment',
                 'income_other_manual', 'income_deposit_refund_total')
    def _compute_other_income_total(self):
        """
        ดึงยอดรวมเงินได้อื่นๆ = other.income.line + actor + bonus + missed + manual + deposit_refund
        แล้ว set income_other = total
        """
        for rec in self:
            total = 0.0
            if rec.employee_id:
                # ✅ เงินได้อื่นๆ ยึด 'รอบตัด 25–24' ของรอบทำเงินเดือน (ไม่ใช่เดือนปฏิทินของวันจ่าย)
                cyc_start, cyc_end = rec._security_deposit_cycle_window()
                if (not cyc_start or not cyc_end) and rec.payment_date:
                    pd = rec.payment_date
                    cyc_start = pd.replace(day=1)
                    cyc_end = pd.replace(day=calendar.monthrange(pd.year, pd.month)[1])
                if cyc_start and cyc_end:
                    lines = self.env['other.income.line'].search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('state', '=', 'confirmed'),
                        ('payment_date', '>=', cyc_start),
                        ('payment_date', '<=', cyc_end),
                    ])
                    total = sum(l.amount for l in lines)
            # บวก: actor + bonus (ถ้าติ๊ก) + missed + manual + deposit refund (พนักงานลาออก)
            other_income_lines_total = total
            actor_val = rec.actor_content_total or 0.0
            bonus_val = (rec.income_bonus or 0.0) if rec.bonus_active else 0.0
            missed_val = rec.income_missed_payment or 0.0
            manual_val = rec.income_other_manual or 0.0
            refund_val = rec.income_deposit_refund_total or 0.0
            total = other_income_lines_total + actor_val + bonus_val + missed_val + manual_val + refund_val
            rec.other_income_total = total
            rec.income_other = total
            emp_code = rec.employee_id.employee_code if rec.employee_id else '-'
            _logger.info(
                "[INCOME_OTHER] emp=%s | lines=%.2f actor=%.2f bonus=%.2f missed=%.2f manual=%.2f refund=%.2f → total=%.2f",
                emp_code, other_income_lines_total, actor_val, bonus_val, missed_val, manual_val, refund_val, total
            )

    def _security_deposit_cycle_window(self):
        """ช่วง 'รอบตัดเงินเดือน' (cutoff cycle) ของ payroll นี้ = (วันเริ่ม, วันสิ้นสุด)
        start_day (วันเริ่มรอบ ปกติ 25 ของเดือนก่อน) → end_day (วันตัดรอบ ปกติ 24 ของเดือนนี้)

        ใช้ให้การหักเงินประกัน 'ตามรอบ 25–24' ตรงกับ payroll period — ไม่ใช่เดือนปฏิทิน
        เพราะ payment_date ที่ตกวันที่ 25–สิ้นเดือน ต้องเข้ารอบของเดือนถัดไป
        คืน (None, None) ถ้า month/year ไม่ถูกต้อง"""
        self.ensure_one()
        try:
            m = int(self.month)
            y = int(self.year)
        except (ValueError, TypeError):
            return (None, None)
        end_day = self.cutoff_day or 24
        start_day = (self.period_id.cutoff_start_day if self.period_id else None) or 25
        last_end = calendar.monthrange(y, m)[1]
        end_date = date(y, m, min(end_day, last_end))
        if m == 1:
            prev_m, prev_y = 12, y - 1
        else:
            prev_m, prev_y = m - 1, y
        last_start = calendar.monthrange(prev_y, prev_m)[1]
        start_date = date(prev_y, prev_m, min(start_day, last_start))
        return (start_date, end_date)

    @api.depends('employee_id', 'month', 'year')
    def _compute_deposit_amounts(self):
        """ดึงยอดจาก work.security.deposit แยก 3 ส่วน
        Note: work.security.deposit.* อยู่ใน employee_salary module เดียวกัน
        ไม่ต้อง try/except"""
        Payment = self.env['work.security.deposit.line.payment']
        DepositLine = self.env['work.security.deposit.line']
        for rec in self:
            regular_payments = Payment.browse()
            extra_payments = Payment.browse()
            refund_lines = DepositLine.browse()

            emp_code = rec.employee_id.employee_code if rec.employee_id else '-'
            _logger.info("[DEPOSIT_COMPUTE] emp=%s month=%s year=%s",
                         emp_code, rec.month, rec.year)

            if rec.employee_id and rec.month and rec.year:
                try:
                    m = int(rec.month)
                    y = int(rec.year)
                    last_day = calendar.monthrange(y, m)[1]
                    start_d = date(y, m, 1)
                    end_d = date(y, m, last_day)
                    # ✅ หักเงินประกันใช้ 'รอบตัด 25–24' (cutoff cycle) ไม่ใช่เดือนปฏิทิน
                    #    → payment_date ที่ตกวันที่ 25–สิ้นเดือน เข้ารอบถัดไปถูกต้อง
                    cyc_start, cyc_end = rec._security_deposit_cycle_window()
                    if not cyc_start or not cyc_end:
                        cyc_start, cyc_end = start_d, end_d

                    all_payments = Payment.search([
                        ('line_id.employee_id', '=', rec.employee_id.id),
                        ('line_id.deposit_id.state', '=', 'confirmed'),
                        ('payment_date', '>=', cyc_start),
                        ('payment_date', '<=', cyc_end),
                    ])
                    _logger.info("[DEPOSIT_COMPUTE] emp=%s | cycle=%s..%s | all_payments=%d",
                                 emp_code, cyc_start, cyc_end, len(all_payments))

                    regular_payments = all_payments.filtered(lambda p: p.payment_type == 'regular')
                    extra_payments = all_payments.filtered(lambda p: p.payment_type != 'regular')

                    regular_payments = regular_payments.filtered(
                        lambda p: not (p.line_id.work_status == 'resigned' and p.line_id.resign_date
                                       and p.payment_date > p.line_id.resign_date)
                    )

                    # ✅ คืนเงินประกัน: ลาออกตกรอบตัดไหน คืนรอบนั้น (ใช้ cutoff cycle เหมือนการหัก)
                    refund_lines = DepositLine.search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('deposit_id.state', '=', 'confirmed'),
                        ('work_status', '=', 'resigned'),
                        ('resign_date', '>=', cyc_start),
                        ('resign_date', '<=', cyc_end),
                        ('manual_refunded', '=', False),  # ★ ข้าม line ที่ mark คืนเองแล้ว
                    ])
                    _logger.info("[DEPOSIT_COMPUTE] emp=%s | refund_lines=%d (resigned in cycle %s..%s, ไม่รวม manual_refunded)",
                                 emp_code, len(refund_lines), cyc_start, cyc_end)
                except (ValueError, TypeError) as e:
                    _logger.warning("[DEPOSIT_COMPUTE] error emp=%s: %s", emp_code, e)

            rec.expense_deposit_regular_breakdown_ids = regular_payments if regular_payments else False
            rec.expense_deposit_extra_breakdown_ids = extra_payments if extra_payments else False
            rec.income_deposit_refund_breakdown_ids = refund_lines if refund_lines else False

            rec.expense_deposit_regular_total = sum(regular_payments.mapped('amount')) if regular_payments else 0.0
            rec.expense_deposit_extra_total = sum(extra_payments.mapped('amount')) if extra_payments else 0.0
            refund_total = 0.0
            if refund_lines:
                for line in refund_lines:
                    paid = line.payment_ids.filtered(
                        lambda p: p.is_synced and p.payment_type == 'regular'
                    )
                    refund_total += sum(paid.mapped('amount'))
            rec.income_deposit_refund_total = refund_total

            _logger.info("[DEPOSIT_COMPUTE] emp=%s | regular=%.2f extra=%.2f refund=%.2f",
                         emp_code, rec.expense_deposit_regular_total,
                         rec.expense_deposit_extra_total, refund_total)

    @api.depends('expense_other_manual', 'expense_deposit_regular_total', 'expense_deposit_extra_total')
    def _compute_expense_other_total(self):
        """expense_other (รวม) = manual + deposit_regular + deposit_extra"""
        for rec in self:
            rec.expense_other = ((rec.expense_other_manual or 0.0)
                                 + (rec.expense_deposit_regular_total or 0.0)
                                 + (rec.expense_deposit_extra_total or 0.0))

    @api.depends('employee_id', 'payment_date', 'month', 'year', 'cutoff_day', 'period_id')
    def _compute_other_income_breakdowns(self):
        """รวบรวม records ที่ระบบ "ดึงมาใส่" ในรายได้อื่นๆ — เพื่อแสดงเป็นตารางในฟอร์ม"""
        ManualTimeLog = None
        try:
            ManualTimeLog = self.env['hr.manual.time.log']
        except KeyError:
            pass
        for rec in self:
            # other.income.line — ยึด 'รอบตัด 25–24' ให้ตรงกับ _compute_other_income_total
            other_lines = self.env['other.income.line']
            if rec.employee_id:
                cyc_start, cyc_end = rec._security_deposit_cycle_window()
                if (not cyc_start or not cyc_end) and rec.payment_date:
                    pd = rec.payment_date
                    cyc_start = pd.replace(day=1)
                    cyc_end = pd.replace(day=calendar.monthrange(pd.year, pd.month)[1])
                if cyc_start and cyc_end:
                    other_lines = self.env['other.income.line'].search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('state', '=', 'confirmed'),
                        ('payment_date', '>=', cyc_start),
                        ('payment_date', '<=', cyc_end),
                    ])
            rec.other_income_breakdown_ids = other_lines

            # hr.manual.time.log — actor content ตามรอบตัด
            actor_logs = ManualTimeLog.browse() if ManualTimeLog is not None else False
            if ManualTimeLog is not None and rec.employee_id and rec.month and rec.year:
                try:
                    m = int(rec.month)
                    y = int(rec.year)
                    end_day = rec.cutoff_day or 24
                    start_day = (rec.period_id.cutoff_start_day if rec.period_id else None) or 25
                    last_end = calendar.monthrange(y, m)[1]
                    end_date = date(y, m, min(end_day, last_end))
                    if m == 1:
                        prev_m, prev_y = 12, y - 1
                    else:
                        prev_m, prev_y = m - 1, y
                    last_start = calendar.monthrange(prev_y, prev_m)[1]
                    start_date = date(prev_y, prev_m, min(start_day, last_start))
                    actor_logs = ManualTimeLog.search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('reason_type', '=', 'ค่าตัวนักแสดง ถ่าย content'),
                        ('state', '=', 'อนุมัติ'),
                        ('work_date', '>=', start_date),
                        ('work_date', '<=', end_date),
                    ])
                except (ValueError, TypeError):
                    pass
            rec.actor_content_breakdown_ids = actor_logs if actor_logs else False

    @api.depends('employee_id', 'month', 'year', 'cutoff_day', 'period_id')
    def _compute_actor_content_total(self):
        """ดึงยอดค่าตัวนักแสดง ถ่าย content จาก hr.manual.time.log"""
        try:
            ManualTimeLog = self.env['hr.manual.time.log']
        except KeyError:
            _logger.info("[ACTOR_COMPUTE] hr.manual.time.log model not loaded yet → skip")
            for rec in self:
                rec.actor_content_total = 0.0
            return
        for rec in self:
            total = 0.0
            emp_code = rec.employee_id.employee_code if rec.employee_id else '-'
            if rec.employee_id and rec.month and rec.year:
                try:
                    m = int(rec.month)
                    y = int(rec.year)
                    end_day = rec.cutoff_day or 24
                    start_day = (rec.period_id.cutoff_start_day if rec.period_id else None) or 25

                    last_end = calendar.monthrange(y, m)[1]
                    end_date = date(y, m, min(end_day, last_end))

                    if m == 1:
                        prev_m, prev_y = 12, y - 1
                    else:
                        prev_m, prev_y = m - 1, y
                    last_start = calendar.monthrange(prev_y, prev_m)[1]
                    start_date = date(prev_y, prev_m, min(start_day, last_start))

                    logs = ManualTimeLog.search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('reason_type', '=', 'ค่าตัวนักแสดง ถ่าย content'),
                        ('state', '=', 'อนุมัติ'),
                        ('work_date', '>=', start_date),
                        ('work_date', '<=', end_date),
                    ])
                    total = sum(l.amount or 0.0 for l in logs)
                except (ValueError, TypeError):
                    pass
            rec.actor_content_total = total

    # หมายเหตุ: ลบ constraint/onchange ของ income_other ออก
    # เพราะ income_other = compute เสมอ (ดูใน _compute_other_income_total)
    # user แก้ผ่าน income_other_manual / bonus / missed แทน

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
            if rec.manual_sso_amount and rec.manual_sso_amount > 0:
                rec.sso_total = rec.manual_sso_amount
            else:
                rec.sso_total = sum(l.amount for l in rec.line_ids if l.name == 'ประกันสังคม')

    def _get_tax_income_base(self, ot_amount=None):
        """แยกเงินได้สำหรับคำนวณภาษีออกเป็น 2 ส่วน (= total_gross รวมกัน):
        - recurring : รายได้ "ประจำ" ต่อเดือน (เงินเดือน + OT + เบี้ยเลี้ยงประจำทุกตัว + คอมมิชชั่น)
                      → ระบบคูณ 12 เพื่อประมาณการเงินได้ทั้งปี (วิธีหัก ณ ที่จ่าย)
        - one_time  : รายได้ "ครั้งเดียว/ไม่ประจำ" = income_other
                      (โบนัส + ค่าตัวนักแสดง + เงินตกหล่น + เมนูเงินได้อื่นๆ + เงินคืนประกัน)
                      → บวกเข้าเฉพาะเดือนที่จ่าย ไม่คูณ 12 (กันภาษีพุ่งผิด)
        ⚠️ ใช้ base_salary "เต็ม" (ไม่ prorate) เพื่อให้ฐานภาษีสม่ำเสมอทุกเดือน
        :param ot_amount: ส่ง OT ที่เพิ่งคำนวณสด ๆ มาแทน self.ot_total ได้
                          (ตอน _populate_all_lines ค่า self.ot_total อาจยัง stale)
        """
        self.ensure_one()
        ot = (self.ot_total if ot_amount is None else ot_amount) or 0.0
        recurring = (
            (self.base_salary or 0.0)
            + ot
            + (self.income_cost_of_living or 0.0)
            + (self.income_position_allowance or 0.0)
            + (self.income_experience_allowance or 0.0)
            + (self.income_professional_allowance or 0.0)
            + (self.income_allowance or 0.0)
            + (self.income_food or 0.0)
            + (self.income_transport or 0.0)
            + (self.income_fuel or 0.0)
            + (self.income_commission or 0.0)
            + (self.income_commission_sale or 0.0)
        )
        one_time = self.income_other or 0.0
        return recurring, one_time

    @api.depends('total_gross', 'personal_deduction', 'child_deduction', 'expense_deduction',
                 'provident_fund_rate', 'sso_total', 'tax_bracket_ids', 'line_ids',
                 'manual_tax_amount', 'manual_override_tax',
                 'ded_spouse', 'ded_parents', 'ded_disabled',
                 'ded_life_insurance', 'ded_health_insurance',
                 'ded_parents_health_insurance', 'ded_pension_insurance',
                 'ded_rmf', 'ded_ssf', 'ded_thaiesg', 'ded_pension_fund',
                 'ded_home_loan_interest', 'ded_donation', 'ded_donation_education',
                 'ded_shopping')
    def _compute_tax(self):
        for rec in self:
            # ใช้ [:1] เพื่อรับ singleton — กรณีมี duplicate line
            tax_line = rec.line_ids.filtered(lambda l: l.name == 'ภาษีหัก ณ ที่จ่าย')[:1]
            exec_cfg = rec.EXECUTIVE_TAX_CONFIG.get(rec.employee_code or '')
            # ✅ ติ๊กปรับแก้ด้วยมือ → ยึดค่าที่กรอก
            #    ต้องเช็คก่อนบุคคลพิเศษ ไม่งั้นค่าล็อกใน EXECUTIVE_TAX_CONFIG จะทับค่าที่ผู้ใช้กรอก
            #    แล้วยิงค่าเก่าไป PHP (payroll_report.php อ่าน tax_monthly ตรง ๆ)
            if rec.manual_override_tax:
                rec.tax_monthly = rec.manual_tax_amount
                rec.tax_annual = rec.manual_tax_amount * 12
            elif exec_cfg and exec_cfg.get('tax_monthly') is not None:  # ✅ บุคคลพิเศษ — ล็อกภาษีคงที่
                rec.tax_monthly = exec_cfg['tax_monthly']
                rec.tax_annual = rec.tax_monthly * 12
            elif tax_line and tax_line.amount > 0:  # ✅ ใช้ค่าที่ user override (แก้ใน line ตรงๆ)
                rec.tax_monthly = tax_line.amount
                rec.tax_annual = rec.tax_monthly * 12
            else:
                sso_amount_monthly = rec.sso_total or 0.0
                # ฐานภาษี = รายได้ประจำ (×12) + รายได้ครั้งเดียว/income_other (บวกครั้งเดียว)
                recurring, one_time = rec._get_tax_income_base()
                rec.tax_monthly, rec.tax_annual = rec._calculate_tax(
                    recurring, sso_amount_monthly, one_time)

    def _calculate_tax(self, gross_income, sso_monthly, bonus_amount=0.0):
        """คำนวณภาษีต่อเดือน + ภาษีต่อปี

        :param gross_income: รายได้ "ประจำ" ต่อเดือน (เงินเดือน+OT+เบี้ยเลี้ยงประจำ+คอม) — ระบบคูณ 12
        :param sso_monthly:  ประกันสังคมต่อเดือน
        :param bonus_amount: รายได้ "ครั้งเดียว/ไม่ประจำ" ของเดือนนี้ (โบนัส + income_other ทั้งหมด)
                             — จะถูกรวมเข้า annual_income แบบ "one-time" (ไม่ × 12)
                             — และภาษีส่วนเพิ่มจะถูกหักในเดือนที่จ่ายเท่านั้น
        """
        annual_income = gross_income * 12
        # ลดหย่อน ปกส. ที่หักภาษีได้ = สูงสุด 9,000/ปี ตามกฎหมาย (เพดานฐาน 15,000 × 5% × 12)
        # แม้ระบบหัก ปกส. จากเงินเดือนจริงปีละ 10,500 (ฐาน 17,500) แต่ลดหย่อนภาษีได้แค่ 9,000
        sso_annual = min(sso_monthly * 12, 9000)

        provident_fund_annual = 0
        if self.provident_fund_rate > 0:
            provident_fund_monthly = self.base_salary * (self.provident_fund_rate / 100)
            provident_fund_annual = min(provident_fund_monthly * 12, self.provident_fund_deduction_max)

        def _bracket_tax(taxable):
            for bracket in sorted(self.tax_bracket_ids, key=lambda b: b.sequence, reverse=True):
                if taxable > bracket.income_from:
                    return (taxable * (bracket.rate / 100.0)) - bracket.deduction
            return 0.0

        def _capped_extras(annual_inc, expense_eff):
            """รวมค่าลดหย่อนเพิ่มเติม (กรอกเอง) หลัง "บังคับเพดานตามกฎหมายสรรพากร"
            ป้องกันการกรอกเกินเพดาน → ระบบหักให้ไม่เกินที่กฎหมายอนุญาตเสมอ
            :param annual_inc: เงินได้พึงประเมินทั้งปี (ใช้เป็นฐาน % ของ RMF/SSF/บำนาญ/บริจาค)
            :param expense_eff: ค่าใช้จ่ายที่หักได้จริงปีนั้น (ใช้คำนวณฐานเงินบริจาค)
            ใช้ closure: sso_annual, provident_fund_annual
            """
            inc = annual_inc or 0.0

            # ── กลุ่มครอบครัว ──
            spouse   = min(self.ded_spouse or 0.0, 60000.0)         # คู่สมรสไม่มีเงินได้ ≤ 60,000
            parents  = min(self.ded_parents or 0.0, 120000.0)       # 30,000/คน สูงสุด 4 คน = 120,000
            disabled = self.ded_disabled or 0.0                     # 60,000/คน ไม่จำกัดจำนวนคน

            # ── กลุ่มประกัน ──
            # ประกันสุขภาพตนเอง ≤ 25,000 และ (ชีวิต + สุขภาพตนเอง) รวมกัน ≤ 100,000
            health_self    = min(self.ded_health_insurance or 0.0, 25000.0)
            life_health    = min((self.ded_life_insurance or 0.0) + health_self, 100000.0)
            parents_health = min(self.ded_parents_health_insurance or 0.0, 15000.0)  # ≤ 15,000
            # ประกันชีวิตแบบบำนาญ ≤ 15% ของเงินได้ และ ≤ 200,000
            pension_ins    = min(self.ded_pension_insurance or 0.0, inc * 0.15, 200000.0)

            # ── กลุ่มการลงทุน/เกษียณ (เพดานรายตัว) ──
            rmf      = min(self.ded_rmf or 0.0, inc * 0.30, 500000.0)        # RMF ≤ 30% และ ≤ 500,000
            ssf      = min(self.ded_ssf or 0.0, inc * 0.30, 200000.0)        # SSF ≤ 30% และ ≤ 200,000
            pf_extra = min(self.ded_pension_fund or 0.0, inc * 0.15, 500000.0)  # กองทุนสำรองฯ ≤ 15% และ ≤ 500,000
            # เพดานรวมกลุ่มเกษียณ ≤ 500,000 (บำนาญ + RMF + SSF + กองทุนสำรองฯ กรอกเอง
            # + กองทุนสำรองฯ ที่หักจากอัตรา % provident_fund_annual)
            room   = max(0.0, 500000.0 - provident_fund_annual)
            retire = min(pension_ins + rmf + ssf + pf_extra, room)
            # ThaiESG แยกเพดานต่างหาก (ไม่นับรวม 500,000) ≤ 30% และ ≤ 300,000
            thaiesg = min(self.ded_thaiesg or 0.0, inc * 0.30, 300000.0)

            # ── กลุ่มอื่นๆ ──
            home_loan = min(self.ded_home_loan_interest or 0.0, 100000.0)   # ดอกเบี้ยบ้าน ≤ 100,000
            shopping  = min(self.ded_shopping or 0.0, 50000.0)              # Easy E-Receipt ≤ 50,000

            # เงินบริจาค — หักได้ไม่เกิน 10% ของเงินได้ "หลังหักค่าใช้จ่าย+ลดหย่อนอื่น" (ก่อนบริจาค)
            #   1) บริจาคการศึกษา/กีฬา/รพ.รัฐ (คูณ 2 แล้ว) ≤ 10% ของฐาน
            #   2) บริจาคทั่วไป ≤ 10% ของฐานที่เหลือหลังหักบริจาคการศึกษาแล้ว
            base = max(0.0, inc - expense_eff
                       - self.personal_deduction - self.child_deduction
                       - sso_annual - provident_fund_annual
                       - (spouse + parents + disabled + life_health + parents_health
                          + retire + thaiesg + home_loan + shopping))
            edu_donation = min(self.ded_donation_education or 0.0, base * 0.10)
            gen_donation = min(self.ded_donation or 0.0, (base - edu_donation) * 0.10)

            return (spouse + parents + disabled
                    + life_health + parents_health
                    + retire + thaiesg
                    + home_loan + shopping
                    + edu_donation + gen_donation)

        def _annual_tax(annual_inc):
            expense_eff = min(annual_inc * 0.5, self.expense_deduction)
            extra_deductions = _capped_extras(annual_inc, expense_eff)
            total_ded = (self.personal_deduction + self.child_deduction + extra_deductions
                         + expense_eff + sso_annual + provident_fund_annual)
            net_taxable = max(0, annual_inc - total_ded)
            return _bracket_tax(net_taxable)

        annual_tax_no_bonus = _annual_tax(annual_income)
        monthly_tax_no_bonus = annual_tax_no_bonus / 12

        # ถ้ามีโบนัสเดือนนี้ — หักภาษีโบนัสทั้งก้อนในเดือนนี้
        # (เดือนอื่นไม่กระทบ เพราะ bonus_active=False)
        if bonus_amount > 0:
            annual_tax_with_bonus = _annual_tax(annual_income + bonus_amount)
            bonus_tax = annual_tax_with_bonus - annual_tax_no_bonus
            monthly_tax = monthly_tax_no_bonus + bonus_tax
            annual_tax = annual_tax_with_bonus
        else:
            monthly_tax = monthly_tax_no_bonus
            annual_tax = annual_tax_no_bonus

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
                # accumulated_* เป็น computed field — _onchange_employee_id() ด้านล่าง
                # จะ trigger _compute_accumulated_values ให้อัตโนมัติ ใช้ total_gross + opening
                new_payroll._onchange_employee_id()
        return True

    def action_recalculate_all(self):
        # ✅ รีเฟรช salary snapshot ใน DB ปลายทางก่อนคิดค่าคอม (กัน salary เก่า)
        #    push ครั้งเดียวต่อ "งวดค่าคอม" ที่พบใน records ที่เลือก
        Helper = self.env['cross_db.commission.query']
        pushed = set()
        for rec in self:
            try:
                period = rec._get_commission_period()
            except Exception:
                continue
            if period in pushed:
                continue
            pushed.add(period)
            try:
                Helper.push_salary_snapshot(period[0], period[1])
            except Exception as e:
                _logger.warning("[RECALC] push salary snapshot %s ล้มเหลว (ข้าม): %s", period, e)

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

    ACTOR_NAME = 'ค่าตัวนักแสดง ถ่าย content'

    payroll_id = fields.Many2one("payroll.salary", string="Payroll", required=True, ondelete="cascade")
    name = fields.Char(string="รายการ")
    type = fields.Selection([('income', 'รายได้'), ('deduction', 'รายการหัก')], string="ประเภทรายการ", required=True)
    amount = fields.Float(string="จำนวนเงิน", required=True)

    def write(self, vals):
        # ถ้าแก้ amount ของบรรทัด "ค่าตัวนักแสดง ถ่าย content" → ปรับ income_other ของ parent
        # ตามผลต่าง เพื่อให้ field income_other / other_income_total / total ตรงกัน
        deltas = {}
        if 'amount' in vals:
            for line in self:
                if (line.payroll_id and line.name == self.ACTOR_NAME
                        and line.type == 'income'):
                    delta = (vals['amount'] or 0.0) - (line.amount or 0.0)
                    if delta:
                        deltas[line.payroll_id.id] = deltas.get(line.payroll_id.id, 0.0) + delta
        res = super().write(vals)
        for payroll_id, delta in deltas.items():
            payroll = self.env['payroll.salary'].browse(payroll_id)
            payroll.write({'income_other': (payroll.income_other or 0.0) + delta})
        return res


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


class PayrollDeductionLine(models.Model):
    _name = 'payroll.deduction.line'
    _description = 'รายละเอียดการหัก (ขาด/ลา/สาย/ออกก่อนเวลา)'
    _order = 'date, category'

    payroll_id = fields.Many2one('payroll.salary', string='Payroll', ondelete='cascade')
    date = fields.Date(string='วันที่')
    day_name = fields.Char(string='วัน')
    category = fields.Selection([
        ('late', 'มาสาย'),
        ('early', 'ออกก่อนเวลา'),
        ('absent', 'ขาดงาน'),
        ('leave', 'ลา'),
    ], string='ประเภท')
    description = fields.Char(string='รายละเอียด')
    time_detail = fields.Char(string='เวลา')
    minutes = fields.Float(string='นาที')
    amount = fields.Float(string='ยอดหัก (บาท)')
