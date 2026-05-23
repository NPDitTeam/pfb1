# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class SaturdayLeaveConfig(models.Model):
    _name = 'saturday.leave.config'
    _description = 'กำหนดสิทธิหยุดวันเสาร์'
    _order = 'branch_id'

    branch_id = fields.Many2one(
        'hr.branch.custom', string='สาขา',
        required=True, ondelete='cascade')
    days_allowed = fields.Integer(
        string='สิทธิหยุดวันเสาร์/เดือน (ครั้ง)', default=1, required=True,
        help='ค่าเริ่มต้นของทั้งสาขา — ปรับรายบุคคลได้ที่ตารางพนักงานด้านล่าง')
    employee_line_ids = fields.One2many(
        'saturday.leave.employee', 'config_id',
        string='สิทธิหยุดวันเสาร์รายบุคคล (override)')
    employee_override_count = fields.Integer(
        string='พนักงาน (คน)', compute='_compute_employee_override_count')

    _sql_constraints = [
        ('branch_uniq', 'unique(branch_id)',
         'สาขานี้มีการตั้งค่าสิทธิหยุดวันเสาร์อยู่แล้ว'),
    ]

    @api.depends('employee_line_ids')
    def _compute_employee_override_count(self):
        for rec in self:
            rec.employee_override_count = len(rec.employee_line_ids)

    def write(self, vals):
        """เมื่อแก้ค่าระดับสาขา (days_allowed) → cascade ไปยังบรรทัดพนักงาน
        ที่ยังเป็นค่า default เดิมของสาขา (ถือว่าไม่ได้ปรับรายบุคคล)
        — บรรทัดที่ตั้งค่าเฉพาะคนไว้ (ค่าต่างจาก default เดิม) จะไม่ถูกแตะ"""
        cascade_map = {}
        if 'days_allowed' in vals:
            new_val = vals['days_allowed']
            for rec in self:
                if rec.days_allowed != new_val:
                    cascade_map[rec.id] = (rec.days_allowed, new_val)
        res = super(SaturdayLeaveConfig, self).write(vals)
        for rec in self:
            if rec.id in cascade_map:
                old_val, new_val = cascade_map[rec.id]
                lines = rec.employee_line_ids.filtered(
                    lambda l: l.days_allowed == old_val)
                if lines:
                    lines.write({'days_allowed': new_val})
        return res

    # ค่าเริ่มต้น: สำนักงานใหญ่ = 2, สาขาอื่น = 1
    DEFAULT_HQ_DAYS = 2
    DEFAULT_OTHER_DAYS = 1

    @api.model
    def _is_head_office(self, branch):
        """ตรวจว่าสาขาเป็นสำนักงานใหญ่ไหม (รองรับการสะกดหลายแบบ — ให้ตรงกับฝั่งแอป)"""
        name = (branch.name or '').strip()
        upper = name.upper()
        return ('สำนักงานใหญ่' in name or 'สนง.ใหญ่' in name or 'สนง ใหญ่' in name
                or upper == 'HQ' or upper == 'HEAD OFFICE')

    @api.model
    def _default_days_for_branch(self, branch):
        return self.DEFAULT_HQ_DAYS if self._is_head_office(branch) else self.DEFAULT_OTHER_DAYS

    @api.model
    def _seed_missing_branches(self):
        """สร้าง config สำหรับสาขาที่ยังไม่มี โดยตั้งค่าเริ่มต้นตามชนิดสาขา
        (ไม่แตะค่าที่ผู้ใช้ปรับไว้แล้ว)"""
        branches = self.env['hr.branch.custom'].sudo().search([])
        existing_branch_ids = set(self.sudo().search([]).mapped('branch_id').ids)
        for b in branches:
            if b.id not in existing_branch_ids:
                self.sudo().create({
                    'branch_id': b.id,
                    'days_allowed': self._default_days_for_branch(b),
                })

    @api.model
    def _seed_employee_lines(self, configs=None):
        """ดึงพนักงานทุกคนตาม employee.salary.branch_id มาแสดงในสาขาของตน
        - configs=None → ทำทุกสาขา / ส่ง recordset มา → ทำเฉพาะสาขานั้น
        - คนที่ยังไม่มีบรรทัด → สร้างใหม่ (ค่าเริ่มต้น = ค่าของสาขา)
        - คนที่ย้ายสาขา (บรรทัดอยู่คนละสาขากับ branch_id ปัจจุบัน) → ย้ายบรรทัดตามสาขาใหม่
          (คงค่า days_allowed เดิมที่เคยตั้งไว้)
        """
        EmpLine = self.env['saturday.leave.employee'].sudo()
        Emp = self.env['employee.salary'].sudo()
        if configs is None:
            configs = self.sudo().search([])
        for cfg in configs:
            if not cfg.branch_id:
                continue
            emps = Emp.search([('branch_id', '=', cfg.branch_id.id)])
            for e in emps:
                line = EmpLine.search([('employee_id', '=', e.id)], limit=1)
                if not line:
                    EmpLine.create({
                        'config_id': cfg.id,
                        'employee_id': e.id,
                        'days_allowed': cfg.days_allowed,
                    })
                elif line.config_id.id != cfg.id:
                    # พนักงานย้ายสาขา → ย้ายบรรทัดไปสาขาปัจจุบัน
                    line.config_id = cfg.id

    @api.model
    def action_sync_and_open(self):
        """ใช้กับเมนู: ดึงสาขาล่าสุด → seed config สาขา → seed พนักงานตามสาขา → เปิดตาราง"""
        # ดึงสาขาล่าสุดจาก PHP API ก่อน (กันสาขาใหม่ตกหล่น) — ถ้าล้มเหลวก็ใช้ที่มีอยู่
        try:
            self.env['hr.branch.custom'].sudo().sync_all_from_api()
        except Exception as e:
            _logger.warning("[SaturdayLeaveConfig] sync สาขาจาก API ไม่สำเร็จ: %s", e)
        self._seed_missing_branches()
        self._seed_employee_lines()
        # คืน dict แบบเดียวกับ medical.expense.sync_and_open_view (พิสูจน์แล้วว่าเปิดฟอร์มได้)
        return {
            'type': 'ir.actions.act_window',
            'name': 'กำหนดสิทธิหยุดวันเสาร์',
            'res_model': 'saturday.leave.config',
            'view_mode': 'tree,form',
            'target': 'current',
        }

    def action_pull_employees(self):
        """ดึงพนักงานในสาขานี้มาลงตาราง override (ตั้งค่าเริ่มต้น = ค่าของสาขา)
        เฉพาะคนที่ยังไม่มีในตาราง — แล้วเปิดฟอร์มใหม่ให้เห็นรายการ"""
        self.ensure_one()
        Emp = self.env['employee.salary'].sudo()
        emps = Emp.search([('branch_id', '=', self.branch_id.id)])
        existing = set(self.employee_line_ids.mapped('employee_id').ids)
        EmpLine = self.env['saturday.leave.employee'].sudo()
        for e in emps:
            if e.id not in existing:
                EmpLine.create({
                    'config_id': self.id,
                    'employee_id': e.id,
                    'days_allowed': self.days_allowed,
                })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'saturday.leave.config',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ============================================================
    # API method: ดึงสิทธิหยุดวันเสาร์/เดือน ตามรหัสพนักงาน
    # เรียกจากแอปผ่าน JSON-RPC:
    #   callKw('saturday.leave.config', 'api_get_saturday_quota', [employee_code])
    # ลำดับการตัดสิน: (1) override รายบุคคล → (2) ค่าของสาขา → (3) ค่าเริ่มต้นตามชนิดสาขา
    # คืนค่าเป็น int (จำนวนครั้ง/เดือน)
    # ============================================================
    @api.model
    def api_get_saturday_quota(self, employee_code):
        if not employee_code:
            return self.DEFAULT_OTHER_DAYS
        emp = self.env['employee.salary'].sudo().search(
            [('employee_code', '=', employee_code)], limit=1)
        if not emp:
            return self.DEFAULT_OTHER_DAYS
        # (1) override รายบุคคล (มีน้ำหนักสูงสุด)
        emp_line = self.env['saturday.leave.employee'].sudo().search(
            [('employee_id', '=', emp.id)], limit=1)
        if emp_line:
            return emp_line.days_allowed
        # (2) ค่าตามสาขา
        if emp.branch_id:
            cfg = self.sudo().search([('branch_id', '=', emp.branch_id.id)], limit=1)
            if cfg:
                return cfg.days_allowed
            # (3) ยังไม่ได้ตั้งค่าสาขานี้ → ค่าเริ่มต้นตามชนิดสาขา
            return self._default_days_for_branch(emp.branch_id)
        return self.DEFAULT_OTHER_DAYS


class SaturdayLeaveEmployee(models.Model):
    _name = 'saturday.leave.employee'
    _description = 'สิทธิหยุดวันเสาร์รายบุคคล'
    _order = 'employee_id'

    config_id = fields.Many2one(
        'saturday.leave.config', string='สาขา (config)',
        required=True, ondelete='cascade')
    branch_id = fields.Many2one(
        'hr.branch.custom', string='สาขา',
        related='config_id.branch_id', store=True)
    employee_id = fields.Many2one(
        'employee.salary', string='พนักงาน',
        required=True, ondelete='cascade')
    employee_code = fields.Char(
        string='รหัสพนักงาน', related='employee_id.employee_code', store=True)
    days_allowed = fields.Integer(
        string='สิทธิหยุดวันเสาร์/เดือน (ครั้ง)', default=1, required=True)

    _sql_constraints = [
        ('emp_uniq', 'unique(employee_id)',
         'พนักงานคนนี้ถูกตั้งค่าสิทธิหยุดวันเสาร์รายบุคคลไว้แล้ว'),
    ]
