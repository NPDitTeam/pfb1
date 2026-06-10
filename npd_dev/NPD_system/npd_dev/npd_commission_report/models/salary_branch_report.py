# -*- coding: utf-8 -*-
"""รายงานรายได้รวมตามสาขา — ดึงจาก payroll.salary ของฐานข้อมูล HRMS โดยตรง

กรณีใช้งาน: payroll (ทำเงินเดือน) อยู่คนละ DB กับ DB ที่รันรายงาน
เช่น HRMS เก็บ payroll แต่รายงานอยู่ที่ NPD_Bangkok_New / NPD_Intertrading_New
DB ทั้งหมดอยู่บน PostgreSQL เซิร์ฟเวอร์เดียวกัน → เปิด connection ใหม่ไป DB ต้นทางได้

เปลี่ยนชื่อ DB ต้นทางได้ที่ System Parameter:
  npd.salary_report.source_db   (default: 'HRMS')

โครงสร้าง:
- npd.salary.branch.report       — TransientModel (wizard เลือกเดือน/ปี)
- npd.salary.branch.report.line  — Model (snapshot ผลลัพธ์, เก็บถาวร)
- ir.cron รายวัน                  — auto-refresh "เดือนปัจจุบัน + ย้อนหลัง 1 เดือน" ทุกวัน
"""
import logging
import psycopg2
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)


class SalaryByBranchReport(models.TransientModel):
    _name = 'npd.salary.branch.report'
    _description = 'รายงานรายได้รวมตามสาขา (จาก HRMS)'

    @api.model
    def _get_year_selection(self):
        current_year = fields.Date.today().year
        return [(str(y), str(y)) for y in range(current_year - 5, current_year + 2)]

    month = fields.Selection(
        selection=[
            ('1', 'มกราคม'), ('2', 'กุมภาพันธ์'), ('3', 'มีนาคม'), ('4', 'เมษายน'),
            ('5', 'พฤษภาคม'), ('6', 'มิถุนายน'), ('7', 'กรกฎาคม'), ('8', 'สิงหาคม'),
            ('9', 'กันยายน'), ('10', 'ตุลาคม'), ('11', 'พฤศจิกายน'), ('12', 'ธันวาคม'),
        ],
        string='เดือน', required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    year = fields.Selection(
        selection='_get_year_selection',
        string='ปี', required=True,
        default=lambda self: str(fields.Date.today().year),
    )

    def action_generate_report(self):
        """ปุ่ม "ดูรายงาน" บน wizard → รีเฟรช snapshot ของเดือน/ปีที่เลือก แล้วเปิด tree"""
        self.ensure_one()
        return self.refresh_for(int(self.month), self.year)

    # ============================================================
    # Core: รีเฟรช snapshot ของ (เดือน, ปี) ที่ระบุ
    # ============================================================
    @api.model
    def refresh_for(self, month, year):
        """รีเฟรช snapshot ของเดือน/ปีนี้ — ลบของเก่าเฉพาะเดือน/ปีนี้ → สร้างใหม่
        เก็บประวัติเดือนอื่นไว้ ไม่ลบ
        :param month: int (1..12)
        :param year:  str หรือ int (จะ cast เป็น str)
        :return: ir.actions.act_window เปิด tree view กรองเดือน/ปีที่รีเฟรช
        """
        month = int(month)
        year = str(year)
        rows = self._fetch_salary_from_source_db(month, year)
        Line = self.env['npd.salary.branch.report.line'].sudo()
        # ลบ snapshot เก่าเฉพาะของเดือน/ปีนี้
        Line.search([('month', '=', month), ('year', '=', year)]).unlink()
        now = fields.Datetime.now()
        if rows:
            Line.create([{
                'month': month,
                'year': year,
                'branch_name': r['branch_name'],
                'employee_count': r['employee_count'],
                'total_income': r['total_income'],
                'last_refresh': now,
            } for r in rows])
        return {
            'name': 'รายได้รวมตามสาขา - %02d/%s' % (month, year),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.salary.branch.report.line',
            'view_mode': 'tree',
            'target': 'current',
            'domain': [('month', '=', month), ('year', '=', year)],
        }

    @api.model
    def cron_refresh_current_month(self):
        """Cron รายวัน — รีเฟรช snapshot ของ "เดือนปัจจุบัน" และ "ย้อนหลัง 1 เดือน"
        รองรับกรณีปิดงวดเงินเดือนของเดือนก่อนในช่วงต้นเดือนถัดไป
        (ชื่อ method คงเดิมเพื่อไม่ต้องแก้ ir.cron record)
        """
        today = fields.Date.today()
        # (เดือนปัจจุบัน, ย้อนหลัง 1 เดือน) — จัดการข้ามปีให้ถูกต้อง
        periods = [(today.month, today.year)]
        if today.month == 1:
            periods.append((12, today.year - 1))
        else:
            periods.append((today.month - 1, today.year))

        for m, y in periods:
            try:
                self.refresh_for(m, str(y))
                _logger.info("[SALARY-BRANCH-REPORT][CRON] รีเฟรชเดือน %d/%s สำเร็จ", m, y)
            except Exception as e:
                # ไม่ raise ใน cron — แค่ log เพื่อไม่ให้ cron crash ทั้งระบบ
                # เดือนหนึ่งล้มเหลวก็ยังพยายามรีเฟรชอีกเดือนต่อ
                _logger.exception("[SALARY-BRANCH-REPORT][CRON] รีเฟรชเดือน %d/%s ล้มเหลว: %s", m, y, e)

    # ============================================================
    # Cross-DB query ไปยัง HRMS
    # ============================================================
    @api.model
    def _get_source_db_name(self):
        """ชื่อ DB ต้นทางที่เก็บ payroll — แก้ผ่าน System Parameter โดยไม่ต้องแก้โค้ด"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'npd.salary_report.source_db', default='HRMS')

    @api.model
    def _get_report_company(self):
        """ชื่อบริษัทที่ DB นี้ต้องกรอง (= ค่าใน employee.salary.company)
        ตั้งค่าต่อ DB ที่ System Parameter: npd.salary_report.company
        เช่น DB NPD_Bangkok_New ตั้งเป็น 'นภดลกรุงเทพจำกัด'
        ถ้าเว้นว่าง → ไม่กรองบริษัท (รวมทุกบริษัทใน HRMS เหมือนเดิม)
        """
        company = self.env['ir.config_parameter'].sudo().get_param(
            'npd.salary_report.company', default='')
        return (company or '').strip()

    def _fetch_salary_from_source_db(self, month, year):
        """เปิด connection แยก ไป DB ต้นทาง (HRMS) → query payroll_salary
        คืน list[dict]: branch_name, employee_count, total_income
                       (= total_gross − คอมมิชชั่นสาขา − คอมมิชชั่น Sale)
        """
        source_db = self._get_source_db_name()
        company = self._get_report_company()
        conn_params = {
            'dbname': source_db,
            'user': config.get('db_user') or 'odoo',
            'password': config.get('db_password') or '',
            'host': config.get('db_host') or 'localhost',
            'port': config.get('db_port') or 5432,
        }
        conn_params = {k: v for k, v in conn_params.items() if v not in (None, '', False)}

        _logger.info("[SALARY-BRANCH-REPORT] เชื่อม DB ต้นทาง '%s' (host=%s) month=%s year=%s company=%s",
                     source_db, conn_params.get('host', '-'), month, year, company or '(ทุกบริษัท)')
        if not company:
            _logger.warning("[SALARY-BRANCH-REPORT] ไม่ได้ตั้ง System Parameter "
                            "'npd.salary_report.company' → ดึง salary รวมทุกบริษัท "
                            "(ยอดอาจพองเพราะรวมบริษัทอื่นในสาขาเดียวกัน)")

        try:
            conn = psycopg2.connect(**conn_params)
        except psycopg2.Error as e:
            raise UserError(
                "ไม่สามารถเชื่อมต่อฐานข้อมูล '%s' ได้\n\n%s\n\n"
                "ตรวจสอบ:\n"
                "1. ชื่อ DB ที่ System Parameter 'npd.salary_report.source_db' (ปัจจุบัน: %s)\n"
                "2. PostgreSQL user/password ใน Odoo config ต้องมีสิทธิ์เข้า DB นั้น"
                % (source_db, str(e).strip(), source_db))

        # กรองบริษัทตาม System Parameter (ถ้าตั้งไว้) — payroll_salary ไม่มี company
        # ตรงๆ ต้อง JOIN employee_salary แล้วเทียบ es.company
        params = [month, str(year)]
        company_clause = ""
        if company:
            company_clause = "AND es.company = %s"
            params.append(company)

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COALESCE(b.name, '(ไม่ระบุสาขา)') AS branch_name,
                        COUNT(DISTINCT ps.employee_id)    AS employee_count,
                        COALESCE(SUM(
                            COALESCE(ps.total_gross, 0)
                            - COALESCE(ps.income_commission, 0)
                            - COALESCE(ps.income_commission_sale, 0)
                        ), 0) AS total_income
                    FROM payroll_salary ps
                    LEFT JOIN employee_salary es ON es.id = ps.employee_id
                    LEFT JOIN hr_branch_custom b ON b.id = ps.branch_id
                    WHERE ps.month = %s
                      AND ps.year  = %s
                      AND COALESCE(ps.active, TRUE) = TRUE
                      {company_clause}
                    GROUP BY b.id, b.name
                    ORDER BY COALESCE(b.name, 'zzz_ไม่ระบุ')
                """.format(company_clause=company_clause), params)
                fetched = cur.fetchall()
        except psycopg2.Error as e:
            conn.close()
            raise UserError(
                "Query ฐานข้อมูล '%s' ผิดพลาด: %s\n\n"
                "อาจเกิดจากตาราง payroll_salary / employee_salary / hr_branch_custom "
                "ไม่มีใน DB นั้น (DB ต้นทางต้องติดตั้งโมดูล employee_salary)"
                % (source_db, str(e).strip()))
        finally:
            conn.close()

        result = [
            {'branch_name': r[0] or '(ไม่ระบุสาขา)',
             'employee_count': int(r[1] or 0),
             'total_income': float(r[2] or 0.0)}
            for r in fetched
        ]
        _logger.info("[SALARY-BRANCH-REPORT] ดึงได้ %d สาขา รวมพนักงาน %d คน",
                     len(result), sum(r['employee_count'] for r in result))
        return result


class SalaryByBranchReportLine(models.Model):
    """Snapshot ผลลัพธ์รายงานรายได้รวมตามสาขา (เก็บถาวร — ไม่ใช่ TransientModel)
    มี snapshot 1 แถวต่อ (เดือน, ปี, สาขา) — รีเฟรชใหม่จะลบของเก่าเฉพาะเดือน/ปีนั้นและสร้างใหม่
    """
    _name = 'npd.salary.branch.report.line'
    _description = 'รายงานรายได้ตามสาขา (snapshot)'
    _order = 'year desc, month desc, branch_name'

    month = fields.Integer(string='เดือน', readonly=True, required=True, index=True)
    year = fields.Char(string='ปี', readonly=True, required=True, index=True)
    branch_name = fields.Char(string='สาขา', readonly=True, required=True)
    employee_count = fields.Integer(string='จำนวนพนักงาน', readonly=True)
    total_income = fields.Float(
        string='รายได้รวม (ไม่รวมคอมมิชชั่น)',
        readonly=True, digits=(16, 2),
        help='ผลรวมรายได้ของพนักงานทุกคนในสาขา = total_gross − ค่าคอมมิชชั่นสาขา − ค่าคอมมิชชั่น Sale')
    last_refresh = fields.Datetime(string='อัพเดทล่าสุด', readonly=True)

    # ============================================================
    # ปุ่มรีเฟรชใน tree header
    # ============================================================
    def action_refresh_current_month(self):
        """ปุ่ม "รีเฟรชเดือนปัจจุบัน" บน header ของตาราง — รีเฟรช snapshot เดือน/ปีของวันนี้"""
        today = fields.Date.today()
        return self.env['npd.salary.branch.report'].refresh_for(today.month, str(today.year))

    def action_refresh_this_period(self):
        """ปุ่ม "รีเฟรช snapshot นี้" — รีเฟรช snapshot ของเดือน/ปีของแถวที่เลือกแถวแรก"""
        if not self:
            return self.action_refresh_current_month()
        rec = self[:1]
        return self.env['npd.salary.branch.report'].refresh_for(rec.month, rec.year)

    def action_open_wizard(self):
        """ปุ่ม "เลือกเดือนอื่น" — เปิด wizard ให้ผู้ใช้เลือกเดือน/ปีอื่นแล้วสร้าง snapshot"""
        return {
            'name': 'รายได้รวมตามสาขา',
            'type': 'ir.actions.act_window',
            'res_model': 'npd.salary.branch.report',
            'view_mode': 'form',
            'target': 'new',
        }
