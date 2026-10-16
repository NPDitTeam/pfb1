# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DEFAULT_SSO_BRANCH = '000000'

# จากไฟล์ที่ยื่นจริง ส.ค. 2569 + ไฟล์รหัสสาขาประกันสังคม (จับคู่จากพนักงานในแต่ละชีต)
DEFAULT_CONFIGS = [
    ('นภดลเอสกรุ๊ปจำกัด', '1002241367', [
        ('200002', ['พัทยา']),
        ('210005', ['ปลวกแดง']),
        ('300003', ['โคราช-บายพาส']),
        ('320004', ['สุรินทร์']),
        ('400001', ['ขอนแก่น-โลตัส', 'มหาสารคาม', 'อุบลราชธานี']),
        ('410007', ['อุดรธานี']),
    ]),
    ('นภดลกรุงเทพจำกัด', '7300103901', [
        ('500001', ['เชียงใหม่']),
        ('740003', ['พระราม2']),
    ]),
    ('นภดลอินเตอร์เทรดดิ้งจำกัด', '1002261635', []),
    ('เอ็นพีดีโลจิสติกส์จำกัด', '1320023614', []),
    ('เอ็นพีดีสตีลเทคจำกัด', '7400147765', []),
]


def _hrms_companies(self):
    return self.env['employee.salary']._fields['company'].selection


class NpdSsoReportConfig(models.Model):
    """ค่าตั้งต้นรายงานประกันสังคม รายบริษัท"""
    _name = 'npd.sso.report.config'
    _description = 'กำหนดค่ารายงานประกันสังคม'
    _order = 'company'
    _rec_name = 'company'

    company = fields.Selection(selection=_hrms_companies, string='บริษัท', required=True)
    employer_account = fields.Char(
        string='เลขที่บัญชีนายจ้าง (สปส.)', size=10,
        help='เลข 10 หลักของบริษัทที่ สปส. ออกให้ ใช้ขึ้นต้นชื่อไฟล์')
    wage_source = fields.Selection([
        ('salary', 'เงินเดือน + เงินเพิ่มประจำ (ค่าครองชีพ/ตำแหน่ง/ประสบการณ์/วิชาชีพ)'),
        ('gross', 'รวมรายได้ทั้งเดือน'),
    ], string='ช่อง "ค่าจ้าง" ดึงจาก', default='salary', required=True,
        help='ไฟล์ตัวอย่างที่ยื่นจริงใช้เงินเดือนเป็นส่วนใหญ่ — เงินสมทบใช้ยอดประกันสังคมในสลิปเสมอ')
    branch_line_ids = fields.One2many('npd.sso.report.branch', 'config_id', string='รหัสสาขา สปส.')
    note = fields.Text(string='หมายเหตุ')

    _sql_constraints = [
        ('company_uniq', 'unique(company)', 'บริษัทนี้มีการกำหนดค่าอยู่แล้ว'),
    ]

    @api.constrains('employer_account')
    def _check_employer_account(self):
        for rec in self:
            if rec.employer_account and not re.fullmatch(r'\d{10}', rec.employer_account):
                raise ValidationError(_('เลขที่บัญชีนายจ้างต้องเป็นตัวเลข 10 หลัก'))

    @api.model
    def _npd_setup_defaults(self):
        Branch = self.env['hr.branch.custom'].with_context(active_test=False)
        for company, account, lines in DEFAULT_CONFIGS:
            if self.search_count([('company', '=', company)]):
                continue
            cmds = [(0, 0, {'sso_branch_code': DEFAULT_SSO_BRANCH, 'is_default': True,
                            'note': 'สาขาที่ไม่ได้จับคู่ไว้ทั้งหมด'})]
            for code, names in lines:
                branches = Branch.search([('name', 'in', names)])
                cmds.append((0, 0, {'sso_branch_code': code, 'branch_ids': [(6, 0, branches.ids)]}))
            self.create({'company': company, 'employer_account': account, 'branch_line_ids': cmds})
        return True

    def sso_branch_code_for(self, branch):
        """รหัสสาขา สปส. ของสาขาเรา — ไม่ได้จับคู่ไว้ = สาขาตั้งต้น (000000)"""
        self.ensure_one()
        for line in self.branch_line_ids:
            if branch and branch in line.branch_ids:
                return line.sso_branch_code
        default = self.branch_line_ids.filtered('is_default')[:1]
        return default.sso_branch_code if default else DEFAULT_SSO_BRANCH


class NpdSsoReportBranch(models.Model):
    """จับคู่รหัสสาขา สปส. กับสาขาของเรา (หนึ่งรหัสได้หลายสาขา)"""
    _name = 'npd.sso.report.branch'
    _description = 'รหัสสาขาประกันสังคม'
    _order = 'config_id, sso_branch_code'

    config_id = fields.Many2one('npd.sso.report.config', required=True, ondelete='cascade')
    sso_branch_code = fields.Char(string='รหัสสาขา สปส.', size=6, required=True)
    branch_ids = fields.Many2many('hr.branch.custom', string='สาขาของเรา')
    is_default = fields.Boolean(
        string='สาขาตั้งต้น', help='พนักงานที่สาขาไม่ได้จับคู่กับรหัสใด จะเข้ารหัสนี้')
    note = fields.Char(string='หมายเหตุ')

    _sql_constraints = [
        ('code_uniq', 'unique(config_id, sso_branch_code)', 'รหัสสาขา สปส. ซ้ำในบริษัทเดียวกัน'),
    ]

    @api.onchange('sso_branch_code')
    def _onchange_code(self):
        for rec in self:
            if rec.sso_branch_code and rec.sso_branch_code.isdigit():
                rec.sso_branch_code = rec.sso_branch_code.zfill(6)

    @api.constrains('sso_branch_code')
    def _check_code(self):
        for rec in self:
            if not re.fullmatch(r'\d{6}', rec.sso_branch_code or ''):
                raise ValidationError(_('รหัสสาขา สปส. ต้องเป็นตัวเลข 6 หลัก (เช่น 000000, 200002)'))

    @api.constrains('branch_ids', 'config_id')
    def _check_branch_once(self):
        for rec in self:
            others = rec.config_id.branch_line_ids - rec
            dup = rec.branch_ids & others.mapped('branch_ids')
            if dup:
                raise ValidationError(_('สาขา %s ถูกจับคู่กับรหัสสาขาอื่นในบริษัทเดียวกันแล้ว')
                                      % ', '.join(dup.mapped('name')))
