# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ApprovalWizard(models.TransientModel):
    _name = 'account.move.approval.wizard'
    _description = "Approval Wizard"

    move_id = fields.Many2one('account.move', required=True, string="เอกสาร")

    # ลองเปลี่ยนจาก related เป็น compute
    requester_id = fields.Many2one(
        'res.users',
        string="ผู้ขออนุมัติ",
        compute='_compute_request_info',
        readonly=True
    )
    request_note = fields.Text(
        string="หมายเหตุการขออนุมัติ",
        compute='_compute_request_info',
        readonly=True
    )

    @api.depends('move_id')
    def _compute_request_info(self):
        for rec in self:
            if rec.move_id:
                rec.requester_id = rec.move_id.create_uid
                rec.request_note = rec.move_id.request_note or ''
            else:
                rec.requester_id = False
                rec.request_note = ''

    approver_id = fields.Many2one(
        'res.users',
        string="ผู้อนุมัติ",
        required=True,
        domain=[('is_active', '=', True)]
    )
    approval_note = fields.Text(string="หมายเหตุการพิจารณา", required=True)
    action = fields.Selection([
        ('approve', 'อนุมัติ'),
        ('revise', 'ส่งกลับแก้ไข')
    ], string="การดำเนินการ", required=True, default='approve')

    @api.model
    def default_get(self, fields):
        res = super(ApprovalWizard, self).default_get(fields)
        active_id = self.env.context.get('active_id')
        if active_id:
            move = self.env['account.move'].browse(active_id)
            res['move_id'] = active_id
            res['approver_id'] = self.env.user.id
            # เพิ่มการ set ค่า default
            res['requester_id'] = move.create_uid.id
            res['request_note'] = move.request_note or ''
        return res

    def action_process(self):
        if self.action == 'approve':
            self.move_id.write({
                'approval_state': 'approved',
                'approver_id': self.approver_id.id,
                'note_approver': self.approval_note,
            })
        else:  # revise
            self.move_id.write({
                'approval_state': 'revise',
                'approver_id': self.approver_id.id,
                'note_approver': self.approval_note,
            })
        return {'type': 'ir.actions.act_window_close'}