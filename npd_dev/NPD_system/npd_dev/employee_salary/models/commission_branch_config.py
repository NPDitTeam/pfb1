# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CommissionBranchConfigLine(models.Model):
    _name = 'commission.branch.config.line'
    _description = 'สัดส่วนค่าคอมมิชชั่นสาขา — รายพนักงาน'
    _order = 'id asc'

    config_id = fields.Many2one(
        'commission.branch.config', string='Config', required=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'employee.salary', string='พนักงาน', required=True,
        ondelete='cascade')
    position_name = fields.Char(
        string='ตำแหน่ง', related='employee_id.position_id.name',
        readonly=True, store=True)
    ratio = fields.Float(string='สัดส่วน', required=True, default=0.0, digits=(16, 2))


class CommissionBranchConfig(models.Model):
    _name = 'commission.branch.config'
    _description = 'ตั้งค่าสัดส่วนค่าคอมมิชชั่นสาขา'
    _order = 'branch_id asc'

    branch_id = fields.Many2one(
        'hr.branch.custom', string='สาขา', required=True,
        ondelete='cascade')
    line_ids = fields.One2many(
        'commission.branch.config.line', 'config_id',
        string='รายชื่อพนักงาน')
    total_ratio = fields.Float(
        string='สัดส่วนรวมทั้งสาขา', digits=(16, 2),
        compute='_compute_total_ratio', store=True)
    employee_count = fields.Integer(
        string='จำนวนพนักงาน',
        compute='_compute_total_ratio', store=True)

    _sql_constraints = [
        ('branch_uniq', 'unique(branch_id)',
         'สาขานี้ถูกตั้งค่าแล้ว! ไม่สามารถสร้างซ้ำได้'),
    ]

    @api.depends('line_ids', 'line_ids.ratio')
    def _compute_total_ratio(self):
        for rec in self:
            rec.total_ratio = sum(rec.line_ids.mapped('ratio'))
            rec.employee_count = len(rec.line_ids)

    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        """เมื่อเลือกสาขา → ดึงพนักงาน active ในสาขานั้นมาเป็น line_ids"""
        if not self.branch_id:
            self.line_ids = [(5, 0, 0)]
            return

        # ดึงพนักงาน active ในสาขาที่เลือก
        employees = self.env['employee.salary'].search([
            ('branch_id', '=', self.branch_id.id),
            ('status', '=', 'active'),
        ])

        # สร้าง lines ใหม่
        lines = []
        for emp in employees:
            lines.append((0, 0, {
                'employee_id': emp.id,
                'ratio': 0.0,
            }))
        self.line_ids = [(5, 0, 0)] + lines

    def action_refresh_employees(self):
        """ปุ่มรีเฟรช — ดึงพนักงาน active ล่าสุด (เพิ่มคนใหม่ ไม่ลบคนเดิม)"""
        self.ensure_one()
        existing_emp_ids = set(self.line_ids.mapped('employee_id').ids)
        employees = self.env['employee.salary'].search([
            ('branch_id', '=', self.branch_id.id),
            ('status', '=', 'active'),
        ])
        new_lines = []
        for emp in employees:
            if emp.id not in existing_emp_ids:
                new_lines.append((0, 0, {
                    'employee_id': emp.id,
                    'ratio': 0.0,
                }))
        if new_lines:
            self.write({'line_ids': new_lines})
        return True

    @api.model
    def get_ratio_for_employee(self, branch_id, employee_id):
        """ดึงสัดส่วนของพนักงานในสาขา ถ้าไม่มี → return 0.0"""
        if not branch_id or not employee_id:
            return 0.0
        line = self.env['commission.branch.config.line'].search([
            ('config_id.branch_id', '=', branch_id),
            ('employee_id', '=', employee_id),
        ], limit=1)
        return line.ratio if line else 0.0

    @api.model
    def get_total_ratio_for_branch(self, branch_id):
        """ดึงสัดส่วนรวมทั้งสาขา"""
        if not branch_id:
            return 0.0
        config = self.search([('branch_id', '=', branch_id)], limit=1)
        return config.total_ratio if config else 0.0
