# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class EmployeeWarning(models.Model):
    _name = 'employee.warning'
    _description = 'ใบเตือนพนักงาน'
    _rec_name = 'employee_id'

    _sql_constraints = [
        ('employee_uniq', 'unique(employee_id)',
         'ไม่สามารถเพิ่มชื่อพนักงานซ้ำได้ ! พนักงานคนนี้มีใบเตือนอยู่แล้ว'),
    ]

    employee_id = fields.Many2one(
        'employee.salary',
        string='ชื่อพนักงาน',
        required=True,
        ondelete='restrict',
    )

    # ฟิลด์ที่ดึงมาจาก employee.salary อัตโนมัติ
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
    branch_id = fields.Many2one(
        'hr.branch.custom',
        string='สาขา',
        related='employee_id.branch_id',
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
    employee_code = fields.Char(
        string='รหัสพนักงาน',
        related='employee_id.employee_code',
        store=True,
        readonly=True,
    )

    warning_line_ids = fields.One2many(
        'employee.warning.line',
        'warning_id',
        string='รายการใบเตือน',
    )

    warning_count = fields.Integer(
        string='จำนวนใบเตือน',
        compute='_compute_warning_count',
        store=True,
    )

    note = fields.Text(string='หมายเหตุ')

    @api.depends('warning_line_ids')
    def _compute_warning_count(self):
        for rec in self:
            rec.warning_count = len(rec.warning_line_ids)

    @api.onchange('warning_line_ids')
    def _onchange_warning_line_ids(self):
        """Renumber warning lines เรียงลำดับ 1, 2, 3, ... ทุกครั้งที่เพิ่ม/ลบ"""
        for idx, line in enumerate(self.warning_line_ids, start=1):
            line.warning_number = idx


class EmployeeWarningLine(models.Model):
    _name = 'employee.warning.line'
    _description = 'รายการใบเตือนพนักงาน'
    _order = 'warning_number asc, id asc'

    warning_id = fields.Many2one(
        'employee.warning',
        string='ใบเตือนพนักงาน',
        required=True,
        ondelete='cascade',
    )

    warning_date = fields.Date(
        string='วันที่ออกใบเตือน',
        required=True,
        default=fields.Date.context_today,
    )

    subject = fields.Char(
        string='เรื่องที่โดนเตือน',
        required=True,
    )

    warning_type = fields.Selection(
        [
            ('verbal', 'ตักเตือนด้วยวาจา'),
            ('written', 'ตักเตือนเป็นหนังสือ'),
        ],
        string='ประเภทใบเตือน',
        required=True,
        default='verbal',
    )

    warning_number = fields.Integer(
        string='จำนวนครั้งออกใบเตือน',
        default=1,
        help='ระบบจะกำหนดเลขครั้งให้อัตโนมัติตามลำดับ',
    )

    warning_number_display = fields.Char(
        string='ครั้งที่',
        compute='_compute_warning_number_display',
    )

    sequence = fields.Integer(string='ลำดับ', default=10)

    attachment = fields.Binary(
        string='ไฟล์แนบใบเตือน',
        attachment=True,
    )
    attachment_filename = fields.Char(string='ชื่อไฟล์แนบ')

    description = fields.Text(string='รายละเอียดเพิ่มเติม')

    @api.depends('warning_number', 'warning_id.warning_line_ids',
                 'warning_id.warning_line_ids.warning_number')
    def _compute_warning_number_display(self):
        for rec in self:
            # ใช้ตำแหน่งในรายการเป็นหลัก เพื่อให้แสดงเลขถูกต้องแม้ว่า warning_number
            # ยังไม่ได้อัพเดท
            position = 0
            if rec.warning_id:
                try:
                    lines = list(rec.warning_id.warning_line_ids)
                    position = lines.index(rec) + 1
                except (ValueError, IndexError):
                    position = rec.warning_number or 0
            if not position:
                position = rec.warning_number or 0
            if position:
                rec.warning_number_display = 'ครั้งที่ %s' % position
            else:
                rec.warning_number_display = ''

    @api.model_create_multi
    def create(self, vals_list):
        """ตั้งเลขครั้งอัตโนมัติตอนสร้างเรคคอร์ดใหม่ (กรณีสร้างผ่าน API)"""
        for vals in vals_list:
            if not vals.get('warning_number') and vals.get('warning_id'):
                existing = self.search_count([('warning_id', '=', vals['warning_id'])])
                vals['warning_number'] = existing + 1
        return super(EmployeeWarningLine, self).create(vals_list)
