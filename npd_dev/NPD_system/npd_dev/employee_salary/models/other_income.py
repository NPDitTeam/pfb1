# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class OtherIncome(models.Model):
    _name = 'other.income'
    _description = 'เงินได้อื่นๆ'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'employee_id'
    _order = 'id desc'

    employee_id = fields.Many2one(
        'employee.salary',
        string='ชื่อพนักงาน',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    employee_code = fields.Char(
        string='รหัสพนักงาน',
        related='employee_id.employee_code',
        store=True,
        readonly=True,
    )
    firstname = fields.Char(
        string='ชื่อ',
        related='employee_id.firstname',
        store=True,
        readonly=True,
    )
    lastname = fields.Char(
        string='นามสกุล',
        related='employee_id.lastname',
        store=True,
        readonly=True,
    )
    position_id = fields.Many2one(
        'hr.position.custom',
        string='ตำแหน่ง',
        related='employee_id.position_id',
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        'hr.department.custom',
        string='แผนก',
        related='employee_id.department_id',
        store=True,
        readonly=True,
    )
    branch_id = fields.Many2one(
        'hr.branch.custom',
        string='สาขา',
        related='employee_id.branch_id',
        store=True,
        readonly=True,
    )

    line_ids = fields.One2many(
        'other.income.line',
        'other_income_id',
        string='รายการเงินได้อื่นๆ',
    )

    total_amount = fields.Float(
        string='ยอดรวมเงินได้อื่นๆ',
        compute='_compute_total_amount',
        store=True,
        tracking=True,
    )

    state = fields.Selection(
        [
            ('draft', 'ร่าง'),
            ('confirmed', 'ยืนยันแล้ว'),
        ],
        string='สถานะ',
        default='draft',
        tracking=True,
    )

    note = fields.Text(string='หมายเหตุเพิ่มเติม')

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(l.amount for l in rec.line_ids)

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('กรุณาเพิ่มรายการเงินได้อื่นๆ ก่อนยืนยัน'))
            for line in rec.line_ids:
                if not line.payment_date or not line.amount:
                    raise UserError(_('กรุณาระบุวันที่จ่ายเงินและจำนวนเงินให้ครบทุกรายการ'))
            rec.state = 'confirmed'
            rec._sync_to_payroll()

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'
            rec._sync_to_payroll()

    def _sync_to_payroll(self):
        """ทริกเกอร์ให้ payroll.salary ของพนักงานรายนี้คำนวณ other_income_total ใหม่
        และสร้าง line 'เงินได้อื่นๆ' ใหม่ใน line_ids"""
        self.ensure_one()
        if not self.employee_id:
            return
        payrolls = self.env['payroll.salary'].search([
            ('employee_id', '=', self.employee_id.id),
        ])
        for payroll in payrolls:
            payroll._compute_other_income_total()
            if not payroll.manual_override:
                payroll._populate_all_lines()
            payroll._compute_total()

    def unlink(self):
        employees = self.mapped('employee_id')
        res = super(OtherIncome, self).unlink()
        if employees:
            payrolls = self.env['payroll.salary'].search([
                ('employee_id', 'in', employees.ids),
            ])
            for payroll in payrolls:
                payroll._compute_other_income_total()
                if not payroll.manual_override:
                    payroll._populate_all_lines()
                payroll._compute_total()
        return res


class OtherIncomeLine(models.Model):
    _name = 'other.income.line'
    _description = 'รายการเงินได้อื่นๆ'
    _order = 'payment_date asc, id asc'

    other_income_id = fields.Many2one(
        'other.income',
        string='เงินได้อื่นๆ',
        required=True,
        ondelete='cascade',
    )

    employee_id = fields.Many2one(
        'employee.salary',
        related='other_income_id.employee_id',
        store=True,
        readonly=True,
    )

    state = fields.Selection(
        related='other_income_id.state',
        store=True,
        readonly=True,
    )

    note = fields.Char(string='หมายเหตุ', required=True)
    amount = fields.Float(string='จำนวนเงิน', required=True)
    payment_date = fields.Date(string='วันที่จ่ายเงิน', required=True,
                               default=fields.Date.context_today)
    attachment = fields.Binary(
        string='ไฟล์แนบ/รูป',
        attachment=True,
    )
    attachment_filename = fields.Char(string='ชื่อไฟล์แนบ')
