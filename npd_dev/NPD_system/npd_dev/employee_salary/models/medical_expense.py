# -*- coding: utf-8 -*-
import requests
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

API_URL = "https://npdhrms.com/api/api_medical_expense.php"


class MedicalExpense(models.Model):
    _name = 'medical.expense'
    _description = 'ค่ารักษาพยาบาล'
    _order = 'created_at desc'
    _rec_name = 'username'

    php_id = fields.Integer(string='PHP ID', readonly=True, index=True)
    employee_id = fields.Many2one('employee.salary', string='พนักงาน', required=True)
    employee_code = fields.Char(related='employee_id.employee_code', string='รหัสพนักงาน', store=True, readonly=True)
    username = fields.Char(string='ชื่อ-นามสกุล', compute='_compute_employee_info', store=True, readonly=True)
    work_date = fields.Date(string='วันที่ทำงาน', default=fields.Date.context_today)
    branch_id = fields.Many2one('hr.branch.custom', string='สาขา',
                                related='employee_id.branch_id', store=True, readonly=True)
    department = fields.Char(string='แผนก', compute='_compute_employee_info', store=True, readonly=True)
    position = fields.Char(string='ตำแหน่ง', compute='_compute_employee_info', store=True, readonly=True)
    amount = fields.Float(string='จำนวนเงิน (บาท)', required=True)
    user_note = fields.Text(string='หมายเหตุจากพนักงาน')
    file_path = fields.Char(string='ไฟล์แนบ (URL จาก PHP)', readonly=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'medical_expense_ir_attachment_rel',
        'expense_id', 'attachment_id',
        string='ไฟล์แนบ',
    )
    state = fields.Selection([
        ('รออนุมัติ', 'รออนุมัติ'),
        ('อนุมัติ', 'อนุมัติ'),
        ('ไม่อนุมัติ', 'ไม่อนุมัติ'),
        ('ยกเลิก', 'ยกเลิก'),
    ], string='สถานะ', default='รออนุมัติ', readonly=True)
    reason = fields.Text(string='เหตุผลจากผู้อนุมัติ')
    created_at = fields.Datetime(string='วันที่ส่งคำขอ', default=fields.Datetime.now, readonly=True)
    approved_at = fields.Datetime(string='วันที่อนุมัติ', readonly=True)

    @api.constrains('php_id')
    def _check_unique_php_id(self):
        for rec in self:
            if rec.php_id:
                duplicate = self.sudo().search([
                    ('php_id', '=', rec.php_id),
                    ('id', '!=', rec.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError("ข้อมูลนี้มีอยู่แล้วในระบบ (PHP ID ซ้ำ)")

    # ============================================================
    # Auto-fill ข้อมูลจาก employee.salary เมื่อเลือกพนักงาน
    # ============================================================
    @api.depends('employee_id')
    def _compute_employee_info(self):
        for rec in self:
            emp = rec.employee_id
            if emp:
                rec.username = ' '.join(filter(None, [
                    emp.prefix_th or '',
                    emp.firstname or '',
                    emp.lastname or '',
                ])).strip()
                rec.department = emp.department_id.name if emp.department_id else ''
                rec.position = emp.position_id.name if emp.position_id else ''
            else:
                rec.username = ''
                rec.department = ''
                rec.position = ''

    # ============================================================
    # อนุมัติ
    # ============================================================
    def action_approve(self):
        for rec in self:
            if rec.state != 'รออนุมัติ':
                raise UserError("สามารถอนุมัติได้เฉพาะคำขอที่สถานะ 'รออนุมัติ' เท่านั้น")
            rec._sync_state_to_php('approve')
            rec.sudo().write({
                'state': 'อนุมัติ',
                'approved_at': fields.Datetime.now(),
                'reason': '',
            })

    # ============================================================
    # ไม่อนุมัติ — เปิด popup ถามเหตุผล
    # ============================================================
    def action_reject(self):
        self.ensure_one()
        if self.state != 'รออนุมัติ':
            raise UserError("สามารถไม่อนุมัติได้เฉพาะคำขอที่สถานะ 'รออนุมัติ' เท่านั้น")
        return {
            'type': 'ir.actions.act_window',
            'name': 'ไม่อนุมัติค่ารักษาพยาบาล',
            'res_model': 'medical.expense.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_expense_id': self.id},
        }

    # ============================================================
    # ยกเลิก
    # ============================================================
    def action_cancel(self):
        for rec in self:
            rec._sync_state_to_php('cancel')
            rec.sudo().write({
                'state': 'ยกเลิก',
                'approved_at': fields.Datetime.now(),
            })

    # ============================================================
    # เปิดไฟล์แนบ (URL จาก PHP เดิม)
    # ============================================================
    def action_open_attachment(self):
        self.ensure_one()
        if not self.file_path:
            raise UserError("ไม่มีไฟล์แนบ")

        base_url = 'https://npdhrms.com/api/'
        file_url = self.file_path
        if not file_url.startswith('http'):
            file_url = base_url + file_url

        return {
            'type': 'ir.actions.act_url',
            'url': file_url,
            'target': 'new',
        }

    # ============================================================
    # Sync state กลับไป PHP — เฉพาะ record ที่มาจาก PHP เท่านั้น
    # ============================================================
    def _sync_state_to_php(self, action, reason=''):
        self.ensure_one()
        if not self.php_id:
            return
        try:
            payload = {
                'request_id': self.php_id,
                'action': action,
                'reason': reason or '',
            }
            _logger.info("Medical Expense sync to PHP: %s", payload)

            response = requests.post(API_URL, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get('status') != 'success':
                raise UserError("API Error: %s" % result.get('message', 'Unknown error'))

        except requests.exceptions.RequestException as e:
            _logger.error("Failed to sync medical expense to PHP (ID=%s): %s", self.php_id, e)
            raise UserError("ไม่สามารถอัพเดทสถานะไป PHP ได้: %s" % e)


class MedicalExpenseRejectWizard(models.TransientModel):
    _name = 'medical.expense.reject.wizard'
    _description = 'Wizard ไม่อนุมัติค่ารักษาพยาบาล'

    expense_id = fields.Many2one('medical.expense', string='คำขอ', required=True)
    reason = fields.Text(string='เหตุผลในการไม่อนุมัติ', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.reason:
            raise UserError("กรุณากรอกเหตุผล")
        expense = self.expense_id
        expense._sync_state_to_php('reject', reason=self.reason)
        expense.sudo().write({
            'state': 'ไม่อนุมัติ',
            'reason': self.reason,
            'approved_at': fields.Datetime.now(),
        })
