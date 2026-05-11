# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AdvanceClearApproverWizard(models.TransientModel):
    _name = 'advance.clear.approver.wizard'
    _description = 'Advance Clear Approver Wizard'

    advance_clear_id = fields.Many2one(
        comodel_name='account.advance.clear',
        string='Advance Clear',
        required=True,
        readonly=True,
    )
    
    approver_note = fields.Text(
        string='หมายเหตุการตรวจสอบ',
        help='กรอกหมายเหตุในการตรวจสอบ (ถ้ามี)'
    )

    def action_confirm_approver(self):
        """Confirm approver with current logged in user and note"""
        self.ensure_one()
        
        if not self.env.user.is_advance_clear_approver:
            raise UserError(_('คุณไม่มีสิทธิ์ในการยืนยันผู้ตรวจสอบ'))
        
        self.advance_clear_id.write({
            'approver_id': self.env.user.id,
            'approver_date': fields.Datetime.now(),
            'approver_note': self.approver_note,
            'is_approved': True,
        })
        
        return {'type': 'ir.actions.act_window_close'}
