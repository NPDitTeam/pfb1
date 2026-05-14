# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AllowanceManagement(models.Model):
    _name = 'allowance.management'
    _description = 'จัดการค่าเบี้ยเลี้ยง'
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(
        string='ชื่อรายการ',
        required=True,
        default=lambda self: _('ค่าเบี้ยเลี้ยง %s') % fields.Date.context_today(self).strftime('%Y-%m-%d'),
    )
    branch_ids = fields.Many2many(
        'hr.branch.custom',
        'allowance_management_branch_rel',
        'allowance_id', 'branch_id',
        string='สาขา',
        required=True,
        help='เลือกได้มากกว่า 1 สาขา กรณีที่ประเภทและราคาเหมือนกัน',
    )
    line_ids = fields.One2many(
        'allowance.management.line',
        'allowance_id',
        string='รายการประเภทค่าเบี้ยเลี้ยง',
    )
    state = fields.Selection([
        ('รออนุมัติ', 'รออนุมัติ'),
        ('อนุมัติ', 'อนุมัติ'),
        ('ไม่อนุมัติ', 'ไม่อนุมัติ'),
        ('ยกเลิก', 'ยกเลิก'),
    ], string='สถานะ', default='รออนุมัติ', readonly=True, tracking=True)
    reason = fields.Text(string='เหตุผลจากผู้อนุมัติ')
    approved_by = fields.Many2one('res.users', string='ผู้อนุมัติ', readonly=True)
    approved_at = fields.Datetime(string='วันที่อนุมัติ', readonly=True)
    created_at = fields.Datetime(string='วันที่สร้าง', default=fields.Datetime.now, readonly=True)

    # ============================================================
    # อนุมัติ
    # ============================================================
    def action_approve(self):
        for rec in self:
            if rec.state != 'รออนุมัติ':
                raise UserError("สามารถอนุมัติได้เฉพาะรายการที่สถานะ 'รออนุมัติ' เท่านั้น")
            if not rec.line_ids:
                raise UserError("กรุณาเพิ่มรายการประเภทค่าเบี้ยเลี้ยงก่อนอนุมัติ")
            if not rec.branch_ids:
                raise UserError("กรุณาเลือกสาขาก่อนอนุมัติ")
            rec.sudo().write({
                'state': 'อนุมัติ',
                'approved_by': self.env.user.id,
                'approved_at': fields.Datetime.now(),
                'reason': '',
            })

    # ============================================================
    # ไม่อนุมัติ — popup ถามเหตุผล
    # ============================================================
    def action_reject(self):
        self.ensure_one()
        if self.state != 'รออนุมัติ':
            raise UserError("สามารถไม่อนุมัติได้เฉพาะรายการที่สถานะ 'รออนุมัติ' เท่านั้น")
        return {
            'type': 'ir.actions.act_window',
            'name': 'ไม่อนุมัติรายการค่าเบี้ยเลี้ยง',
            'res_model': 'allowance.management.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_allowance_id': self.id},
        }

    # ============================================================
    # ยกเลิก
    # ============================================================
    def action_cancel(self):
        for rec in self:
            rec.sudo().write({
                'state': 'ยกเลิก',
                'approved_by': self.env.user.id,
                'approved_at': fields.Datetime.now(),
            })

    # ============================================================
    # กลับเป็นรออนุมัติ (reset)
    # ============================================================
    def action_reset_draft(self):
        for rec in self:
            rec.sudo().write({
                'state': 'รออนุมัติ',
                'approved_by': False,
                'approved_at': False,
                'reason': '',
            })

    # ============================================================
    # API method: ดึงรายการประเภทค่าเบี้ยเลี้ยงตามรหัสพนักงาน
    # เรียกจากแอปผ่าน JSON-RPC: callKw('allowance.management', 'api_get_allowances_by_employee_code', [employee_code])
    # ============================================================
    @api.model
    def api_get_allowances_by_employee_code(self, employee_code):
        if not employee_code:
            return []
        emp = self.env['employee.salary'].sudo().search(
            [('employee_code', '=', employee_code)], limit=1
        )
        if not emp or not emp.branch_id:
            return []
        records = self.sudo().search([
            ('state', '=', 'อนุมัติ'),
            ('branch_ids', 'in', [emp.branch_id.id]),
        ])
        # เลือกราคาตามสัญชาติ: ต่างชาติ → amount_foreign, อื่น ๆ (ไทย/ไม่ระบุ) → amount
        is_foreign = (emp.nationality == 'ต่างชาติ')
        result = []
        seen = set()
        for rec in records:
            for line in rec.line_ids:
                key = (line.name or '').strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                amount_val = line.amount_foreign if is_foreign else line.amount
                has_amount = bool(amount_val and amount_val > 0)
                result.append({
                    'name': line.name or '',
                    'amount': float(amount_val) if has_amount else None,
                    'has_amount': has_amount,
                    'note': line.note or '',
                })
        return result


class AllowanceManagementLine(models.Model):
    _name = 'allowance.management.line'
    _description = 'รายการประเภทค่าเบี้ยเลี้ยง'
    _order = 'id asc'

    allowance_id = fields.Many2one(
        'allowance.management',
        string='จัดการค่าเบี้ยเลี้ยง',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(string='ประเภทค่าเบี้ยเลี้ยง', required=True)
    amount = fields.Float(
        string='ราคา (บาท) ไทย',
        help='สำหรับพนักงานสัญชาติไทย — เว้นว่างได้ผู้ใช้แอปจะกรอกเองตอนเลือก',
    )
    amount_foreign = fields.Float(
        string='ราคา (บาท) ต่างชาติ',
        help='สำหรับพนักงานสัญชาติต่างชาติ — เว้นว่างได้ผู้ใช้แอปจะกรอกเองตอนเลือก',
    )
    note = fields.Text(string='หมายเหตุ')
    state = fields.Selection(
        related='allowance_id.state',
        store=True,
        readonly=True,
    )


class AllowanceManagementRejectWizard(models.TransientModel):
    _name = 'allowance.management.reject.wizard'
    _description = 'Wizard ไม่อนุมัติค่าเบี้ยเลี้ยง'

    allowance_id = fields.Many2one('allowance.management', string='รายการ', required=True)
    reason = fields.Text(string='เหตุผลในการไม่อนุมัติ', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.reason:
            raise UserError("กรุณากรอกเหตุผล")
        allowance = self.allowance_id
        allowance.sudo().write({
            'state': 'ไม่อนุมัติ',
            'reason': self.reason,
            'approved_by': self.env.user.id,
            'approved_at': fields.Datetime.now(),
        })
