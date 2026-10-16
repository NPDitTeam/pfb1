# -*- coding: utf-8 -*-
from odoo import fields, models, tools


def _hrms_companies(self):
    return self.env['employee.salary']._fields['company'].selection


class NpdPayrollMonthlySummary(models.Model):
    """รายงานสรุปรายได้ต่อเดือน — อ่านจากหน้าทำเงินเดือนตรง ๆ (ไม่เก็บข้อมูลซ้ำ)

    นับเฉพาะเดือนที่มีรอบทำเงินเดือน (ไม่ใช่ร่าง) แล้ว เหมือนรายงาน ภ.ง.ด.1 — สลิปที่สร้างเอง
    ก่อนเริ่มใช้รอบ (เดือน 4/2569) ไม่นับ ส่วนสลิปทำนอกรอบในเดือนที่มีรอบแล้วยังนับ"""
    _name = 'npd.payroll.monthly.summary'
    _description = 'รายงานสรุปรายได้ต่อเดือน'
    _auto = False
    _order = 'year desc, month desc, company, employee_code'

    payroll_id = fields.Many2one('payroll.salary', string='สลิป', readonly=True)
    employee_id = fields.Many2one('employee.salary', string='พนักงาน', readonly=True)
    employee_code = fields.Char(string='รหัสพนักงาน', readonly=True)
    taxid = fields.Char(string='เลขผู้เสียภาษี', readonly=True)
    employee_name = fields.Char(string='ชื่อ-สกุล', readonly=True)
    company = fields.Selection(selection=_hrms_companies, string='บริษัท', readonly=True)
    branch_id = fields.Many2one('hr.branch.custom', string='สาขา', readonly=True)
    year = fields.Char(string='ปี', readonly=True)
    month = fields.Integer(string='เดือน', readonly=True, group_operator=False)
    period = fields.Char(string='งวด', readonly=True)
    # รายได้สุทธิ = รวมรายรับในสลิป (ก่อนหักรายการใด ๆ) ตามที่ HR กำหนด
    net_income = fields.Float(string='รายได้สุทธิ', readonly=True)
    sso_total = fields.Float(string='ประกันสังคม', readonly=True)
    tax_monthly = fields.Float(string='ภาษี', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT p.id AS id,
                       p.id AS payroll_id,
                       e.id AS employee_id,
                       e.employee_code AS employee_code,
                       regexp_replace(COALESCE(NULLIF(e.id_card_number, ''), e.passport_number, ''),
                                      '[^0-9A-Za-z]', '', 'g') AS taxid,
                       TRIM(CONCAT_WS(' ', e.prefix_th, e.firstname, e.lastname)) AS employee_name,
                       e.company AS company,
                       e.branch_id AS branch_id,
                       p.year AS year,
                       p.month AS month,
                       CONCAT(p.year, '/', LPAD(p.month::text, 2, '0')) AS period,
                       COALESCE(p.total_gross, 0) AS net_income,
                       COALESCE(p.sso_total, 0) AS sso_total,
                       COALESCE(p.tax_monthly, 0) AS tax_monthly
                  FROM payroll_salary p
                  JOIN employee_salary e ON e.id = p.employee_id
                 WHERE EXISTS (SELECT 1 FROM payroll_period pp
                                WHERE pp.year = p.year AND pp.month = p.month
                                  AND COALESCE(pp.state, '') <> 'draft')
            )
        """ % self._table)
