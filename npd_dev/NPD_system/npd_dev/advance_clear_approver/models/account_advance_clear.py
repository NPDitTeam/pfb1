# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AccountAdvanceClear(models.Model):
    _inherit = 'account.advance.clear'

    approver_id = fields.Many2one(
        comodel_name='res.users',
        string='ผู้ตรวจสอบ',
        readonly=True,
        tracking=True,
        help='ผู้ตรวจสอบที่ได้รับการยืนยัน'
    )
    
    approver_date = fields.Datetime(
        string='วันที่ยืนยัน',
        readonly=True,
        help='วันที่และเวลาที่ยืนยันผู้ตรวจสอบ'
    )
    
    approver_note = fields.Text(
        string='หมายเหตุการตรวจสอบ',
        readonly=True,
        help='หมายเหตุจากผู้ตรวจสอบ'
    )
    
    is_approved = fields.Boolean(
        string='ยืนยันแล้ว',
        default=False,
        readonly=True,
        help='สถานะการยืนยันผู้ตรวจสอบ'
    )
    
    is_current_user_approver = fields.Boolean(
        string='Current User is Approver',
        compute='_compute_is_current_user_approver',
        store=False,
    )

    @api.depends_context('uid')
    def _compute_is_current_user_approver(self):
        """Check if current logged in user is an approver"""
        for rec in self:
            rec.is_current_user_approver = self.env.user.is_advance_clear_approver

    def action_open_approver_wizard(self):
        """Open wizard to confirm approver with note"""
        self.ensure_one()
        
        if not self.env.user.is_advance_clear_approver:
            raise UserError(_('คุณไม่มีสิทธิ์ในการยืนยันผู้ตรวจสอบ'))
        
        return {
            'name': _('ยืนยันผู้ตรวจสอบ'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.clear.approver.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_advance_clear_id': self.id,
            }
        }
    
    def action_reset_approver(self):
        """Reset approver confirmation"""
        self.ensure_one()
        self.write({
            'approver_id': False,
            'approver_date': False,
            'approver_note': False,
            'is_approved': False,
        })
        return True
