# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting for Approval'),
        ('approved', 'Approved'),
        ('revise', 'Need Revision'),
    ], string="Approval State", default='draft')

    approver_id = fields.Many2one(
        'res.users',
        string="Approver",
        domain=[('is_active', '=', True)]
    )

    request_note = fields.Text(string="Request Note")  # เพิ่ม field นี้
    note_approver = fields.Text(string="Approval Note")

    need_approval = fields.Boolean(
        string="Need Approval",
        compute='_compute_need_approval',
        store=False
    )

    @api.depends('reason_code_id', 'invoice_line_ids.price_unit', 'invoice_line_ids.discount_amount')
    def _compute_need_approval(self):
        for move in self:
            need_approval = False
            if move.reason_code_id and move.reason_code_id.name == "สินค้าหาย":
                for line in move.invoice_line_ids:
                    if line.price_unit and line.discount_amount and line.discount_method == 'fix':
                        if line.discount_amount > (line.price_unit * 0.30):
                            need_approval = True
                            break
                    if line.price_unit and line.discount_amount and line.discount_method == 'per':
                        if line.discount_amount > 30:  # discount field เป็นเปอร์เซ็นต์
                            need_approval = True
                            break

            move.need_approval = need_approval

    def action_post(self):
        """Override action_post เพื่อตรวจสอบก่อน Confirm"""
        for move in self:
            if move.need_approval and move.approval_state != 'approved':
                raise UserError("ต้องได้รับการอนุมัติก่อนถึงจะ Confirm ได้")
        return super(AccountMove, self).action_post()