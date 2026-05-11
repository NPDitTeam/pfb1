# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64


class NpdSignature(models.Model):
    _name = 'npd.signature'
    _description = 'ลายเซ็น'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(string='ชื่อลายเซ็น', required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string='พนักงาน', tracking=True)
    user_id = fields.Many2one('res.users', string='ผู้ใช้', default=lambda self: self.env.user, tracking=True)
    
    # ประเภทลายเซ็น
    signature_type = fields.Selection([
        ('draw', 'เซ็นผ่านระบบ'),
        ('text', 'แปลงข้อความเป็นลายเซ็น'),
    ], string='ประเภท', default='draw', required=True, tracking=True)
    
    # ลายเซ็นแบบวาด
    signature_draw = fields.Binary(string='ลายเซ็น (วาด)', attachment=True)
    
    # ลายเซ็นแบบข้อความ
    signature_text = fields.Char(string='ข้อความลายเซ็น')
    signature_font = fields.Selection([
        ('cursive1', 'ลายมือ 1 (Pacifico)'),
        ('cursive2', 'ลายมือ 2 (Dancing Script)'),
        ('cursive3', 'ลายมือ 3 (Great Vibes)'),
        ('cursive4', 'ลายมือ 4 (Allura)'),
        ('cursive5', 'ลายมือ 5 (Sacramento)'),
    ], string='รูปแบบตัวอักษร', default='cursive1')
    signature_color = fields.Char(string='สีลายเซ็น', default='#000080')
    signature_size = fields.Integer(string='ขนาดตัวอักษร', default=48)
    
    # ลายเซ็นที่สร้างจากข้อความ (เก็บเป็น base64 image)
    signature_text_image = fields.Binary(string='ลายเซ็น (ข้อความ)', attachment=True)
    
    # ลายเซ็นสุดท้ายที่ใช้งาน
    signature_final = fields.Binary(string='ลายเซ็นที่ใช้งาน', compute='_compute_signature_final', store=True)
    
    # สถานะ
    is_default = fields.Boolean(string='ลายเซ็นหลัก', default=False, tracking=True)
    active = fields.Boolean(string='ใช้งาน', default=True)
    
    # หมายเหตุ
    note = fields.Text(string='หมายเหตุ')
    
    company_id = fields.Many2one('res.company', string='บริษัท', default=lambda self: self.env.company)

    @api.depends('signature_type', 'signature_draw', 'signature_text_image')
    def _compute_signature_final(self):
        for rec in self:
            if rec.signature_type == 'draw':
                rec.signature_final = rec.signature_draw
            else:
                rec.signature_final = rec.signature_text_image

    @api.onchange('is_default')
    def _onchange_is_default(self):
        """ถ้าตั้งเป็นลายเซ็นหลัก ให้ยกเลิกลายเซ็นหลักอื่น"""
        if self.is_default and self.user_id:
            other_defaults = self.search([
                ('user_id', '=', self.user_id.id),
                ('is_default', '=', True),
                ('id', '!=', self._origin.id if self._origin else False)
            ])
            if other_defaults:
                return {
                    'warning': {
                        'title': _('แจ้งเตือน'),
                        'message': _('จะยกเลิกลายเซ็นหลักเดิมโดยอัตโนมัติ')
                    }
                }

    @api.model
    def create(self, vals):
        """ตั้งค่า default หากเป็นลายเซ็นแรก"""
        res = super(NpdSignature, self).create(vals)
        if res.is_default:
            # ยกเลิก default ของลายเซ็นอื่น
            self.search([
                ('user_id', '=', res.user_id.id),
                ('is_default', '=', True),
                ('id', '!=', res.id)
            ]).write({'is_default': False})
        return res

    def write(self, vals):
        """จัดการเมื่อตั้งเป็น default"""
        res = super(NpdSignature, self).write(vals)
        if vals.get('is_default'):
            for rec in self:
                self.search([
                    ('user_id', '=', rec.user_id.id),
                    ('is_default', '=', True),
                    ('id', '!=', rec.id)
                ]).write({'is_default': False})
        return res

    def action_set_default(self):
        """ตั้งเป็นลายเซ็นหลัก"""
        self.ensure_one()
        # ยกเลิก default ของลายเซ็นอื่นของ user นี้
        self.search([
            ('user_id', '=', self.user_id.id),
            ('is_default', '=', True),
            ('id', '!=', self.id)
        ]).write({'is_default': False})
        self.is_default = True

    def action_preview(self):
        """แสดงตัวอย่างลายเซ็น"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('ตัวอย่างลายเซ็น'),
            'res_model': 'npd.signature',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'preview_mode': True}
        }

    @api.model
    def get_user_default_signature(self, user_id=None):
        """ดึงลายเซ็นหลักของ user"""
        if not user_id:
            user_id = self.env.user.id
        signature = self.search([
            ('user_id', '=', user_id),
            ('is_default', '=', True),
            ('active', '=', True)
        ], limit=1)
        return signature

    def update_text_signature_image(self, image_data):
        """อัพเดทรูปภาพลายเซ็นจากข้อความ (เรียกจาก JavaScript)"""
        self.ensure_one()
        if image_data:
            # ลบ header ของ base64 data URL ถ้ามี
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            self.signature_text_image = image_data
        return True
