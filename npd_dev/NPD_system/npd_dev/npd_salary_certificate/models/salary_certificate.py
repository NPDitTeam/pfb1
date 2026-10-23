# -*- coding: utf-8 -*-
"""หนังสือรับรองเงินเดือน (ผู้ใช้สั่ง 23 ต.ค. 2569)

ช่องที่ไฮไลต์ในแบบฟอร์มดึงจากข้อมูลพนักงาน (employee.salary) — แก้ได้ก่อนพิมพ์
หัวกระดาษตามบริษัทของพนักงาน (ฐาน HRMS เก็บบริษัทเป็น selection ไม่ใช่ res.company จึงตั้งค่าแยก)
ผู้ลงนามเลือกจากรายชื่อที่ตั้งไว้
"""
import re

from odoo import api, fields, models

from .thai_text import baht_text, duration_text, thai_date


def _company_selection(self):
    return self.env['employee.salary']._fields['company'].selection


class NpdSalaryCertCompany(models.Model):
    _name = 'npd.salary.cert.company'
    _description = 'หัวกระดาษหนังสือรับรองเงินเดือน'
    _order = 'sequence, id'
    _rec_name = 'name'

    sequence = fields.Integer(default=10)
    company_key = fields.Selection(_company_selection, string='บริษัทในข้อมูลพนักงาน', required=True)
    name = fields.Char('ชื่อบริษัท (เต็ม)', required=True)
    address = fields.Char('ที่อยู่')
    phone = fields.Char('โทรศัพท์')
    email = fields.Char('อีเมล')
    website = fields.Char('เว็บไซต์')
    logo = fields.Binary('โลโก้', attachment=True)
    footer_text = fields.Char('ข้อความท้ายกระดาษ', default='ฝ่ายบุคคล สำนักงานส่วนกลาง')
    footer_phone = fields.Char('โทรท้ายกระดาษ', default='02-433-5556')

    _sql_constraints = [
        ('company_key_uniq', 'unique(company_key)', 'ตั้งหัวกระดาษของบริษัทนี้ไว้แล้ว'),
    ]


class NpdSalaryCertSigner(models.Model):
    _name = 'npd.salary.cert.signer'
    _description = 'ผู้ลงนามหนังสือรับรองเงินเดือน'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char('ชื่อผู้ลงนาม', required=True)
    title = fields.Char('ตำแหน่ง/ฝ่าย', default='ฝ่ายบุคคล')
    active = fields.Boolean(default=True)


class NpdSalaryCertificate(models.Model):
    _name = 'npd.salary.certificate'
    _description = 'หนังสือรับรองเงินเดือน'
    _inherit = ['mail.thread']
    _order = 'issue_date desc, id desc'

    name = fields.Char('เลขที่/ชื่อ', compute='_compute_name', store=True)
    employee_id = fields.Many2one('employee.salary', string='พนักงาน', required=True, tracking=True)
    issue_date = fields.Date('ออกให้ ณ วันที่', required=True, default=fields.Date.context_today, tracking=True)
    signer_id = fields.Many2one(
        'npd.salary.cert.signer', string='ผู้ลงนาม', required=True,
        default=lambda self: self.env['npd.salary.cert.signer'].search([], limit=1), tracking=True)
    purpose = fields.Char('วัตถุประสงค์ (ไม่พิมพ์)', help='บันทึกไว้ดูภายหลัง เช่น ยื่นกู้ธนาคาร')

    # ดึงจากข้อมูลพนักงาน แก้ได้ก่อนพิมพ์
    company_config_id = fields.Many2one(
        'npd.salary.cert.company', string='หัวกระดาษบริษัท', compute='_compute_from_employee',
        store=True, readonly=False)
    employee_name = fields.Char('ชื่อ-นามสกุล', compute='_compute_from_employee', store=True, readonly=False)
    position_name = fields.Char('ตำแหน่ง', compute='_compute_from_employee', store=True, readonly=False)
    salary = fields.Float('อัตราเงินเดือนล่าสุด', compute='_compute_from_employee', store=True, readonly=False,
                          digits=(16, 2))
    start_date = fields.Date('เริ่มทำงานตั้งแต่วันที่', compute='_compute_from_employee', store=True,
                             readonly=False)

    salary_text = fields.Char('จำนวนเงิน (ตัวอักษร)', compute='_compute_texts')
    start_date_text = fields.Char('วันเริ่มงาน (พ.ศ.)', compute='_compute_texts')
    issue_date_text = fields.Char('วันที่ออก (พ.ศ.)', compute='_compute_texts')
    duration = fields.Char('รวมระยะเวลา', compute='_compute_texts')

    @api.depends('employee_name', 'issue_date')
    def _compute_name(self):
        for rec in self:
            rec.name = 'หนังสือรับรองเงินเดือน %s %s' % (rec.employee_name or '', thai_date(rec.issue_date))

    @staticmethod
    def _clean_position(name):
        # ตำแหน่งในระบบมีภาษาอังกฤษในวงเล็บต่อท้าย เช่น "ผู้จัดการสาขา (Branch Manager)" — หนังสือใช้ภาษาไทย
        return re.sub(r'\s*\([A-Za-z0-9 &/.,\-]+\)\s*$', '', name or '').strip()

    @api.depends('employee_id')
    def _compute_from_employee(self):
        Company = self.env['npd.salary.cert.company']
        for rec in self:
            emp = rec.employee_id
            if not emp:
                continue
            rec.employee_name = '%s%s %s' % (emp.prefix_th or '', emp.firstname or '', emp.lastname or '')
            rec.position_name = self._clean_position(emp.position_id.name)
            rec.salary = emp.salary
            rec.start_date = emp.start_date
            rec.company_config_id = Company.search([('company_key', '=', emp.company)], limit=1)

    @api.depends('salary', 'start_date', 'issue_date')
    def _compute_texts(self):
        for rec in self:
            rec.salary_text = baht_text(rec.salary)
            rec.start_date_text = thai_date(rec.start_date)
            rec.issue_date_text = thai_date(rec.issue_date)
            rec.duration = duration_text(rec.start_date, rec.issue_date)

    def action_print(self):
        return self.env.ref('npd_salary_certificate.action_report_salary_certificate').report_action(self)
