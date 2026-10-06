import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class NpdTaxBranchWizard(models.TransientModel):
    _name = 'npd.tax.branch.wizard'
    _description = 'กรอกรหัสสาขาลูกค้า (Tax Branch)'

    partner_id = fields.Many2one('res.partner', string='ลูกค้า', required=True, readonly=True)
    vat = fields.Char(related='partner_id.vat', string='เลขประจำตัวผู้เสียภาษี')
    branch = fields.Char(string='รหัสสาขา (Tax Branch)', size=5, required=True)

    @api.constrains('branch')
    def _check_branch(self):
        for wizard in self:
            if not re.fullmatch(r'\d{5}', (wizard.branch or '').strip()):
                raise ValidationError(_(
                    'รหัสสาขาต้องเป็นตัวเลข 5 หลัก เช่น 00000 (สำนักงานใหญ่) หรือ 00001'))

    def action_save(self):
        self.ensure_one()
        # พนักงานขายบางคนไม่มีสิทธิ์แก้ผู้ติดต่อ แต่ต้องกรอกช่องนี้ได้
        # จึงเขียนด้วย sudo เฉพาะช่องรหัสสาขาช่องเดียว
        # skip_email_required: partner_email_required ตรวจอีเมลทุกครั้งที่ write
        # ลูกค้าบริษัทที่ยังไม่มีอีเมล (หลายพันราย) จะบันทึกรหัสสาขาไม่ได้เลย
        self.partner_id.sudo().with_context(skip_email_required=True).write(
            {'branch': self.branch.strip()})
        # infos ให้ฝั่ง JS รู้ว่ากรอกแล้ว (ปิดด้วย X / ยกเลิก จะไม่มีค่านี้)
        return {'type': 'ir.actions.act_window_close',
                'infos': {'npd_tax_branch_saved': True}}
