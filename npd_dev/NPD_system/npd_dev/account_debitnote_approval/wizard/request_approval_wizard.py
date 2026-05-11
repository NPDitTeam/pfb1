# -*- coding: utf-8 -*-
from odoo import models, fields, api

class RequestApprovalWizard(models.TransientModel):
    _name = 'account.move.request.approval.wizard'
    _description = "Request Approval Wizard"

    move_id = fields.Many2one('account.move', required=True)
    approver_id = fields.Many2one(
        'res.users',
        string="ผู้อนุมัติ",
        required=True,
        domain=[('is_active', '=', True)]
    )
    request_note = fields.Text(string="หมายเหตุการขออนุมัติ", required=True)

    @api.model
    def default_get(self, fields):
        res = super(RequestApprovalWizard, self).default_get(fields)
        active_id = self.env.context.get('active_id')
        if active_id:
            move = self.env['account.move'].browse(active_id)
            res['move_id'] = active_id
            # ถ้าเป็นการส่งใหม่ ให้เอาผู้อนุมัติเดิม
            if move.approval_state == 'revise' and move.approver_id:
                res['approver_id'] = move.approver_id.id
                res['request_note'] = 'แก้ไขตามคำแนะนำแล้ว'
        return res

    def action_send_approval(self):
        self.move_id.write({
            'approval_state': 'waiting',
            'approver_id': self.approver_id.id,
            'request_note': self.request_note  # เก็บในfield request_note
        })
        return {'type': 'ir.actions.act_window_close'}