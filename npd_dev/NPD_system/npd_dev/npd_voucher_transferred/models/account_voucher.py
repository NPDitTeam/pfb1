# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AccountVoucher(models.Model):
    _inherit = 'account.voucher'

    # ====================================================
    # แก้บัค: method _compute_check_type หายไปจาก account_voucher_npd
    # field check_type_show ประกาศ compute="_compute_check_type" แต่ไม่มี method
    # เพิ่มไว้ที่นี่เพื่อให้ติดตั้งโมดูลได้โดยไม่ต้องแก้ account_voucher_npd
    # ====================================================
    @api.depends('partner_id')
    def _compute_check_type(self):
        for record in self:
            record.check_type_show = 'show' if record.partner_id else ''

    # เพิ่ม state ใหม่ "transferred" (โอนแล้ว)
    state = fields.Selection(
        selection_add=[('transferred', 'โอนแล้ว')],
    )

    # field สถานะโอน (เก็บ Boolean เสริมเผื่อใช้กรองข้อมูล)
    is_transferred = fields.Boolean(
        string='โอนแล้ว',
        default=False,
        copy=False,
        tracking=True,
    )

    # field สถานะการโอน (แสดงข้อความบน form)
    transfer_status = fields.Selection([
        ('not_transferred', 'ยังไม่โอน'),
        ('transferred', 'โอนเงินแล้ว'),
    ], string='สถานะการโอน',
        default='not_transferred',
        copy=False,
        readonly=True,
        tracking=True,
    )

    # วันที่โอน
    transfer_date = fields.Datetime(
        string='วันที่โอน',
        copy=False,
        readonly=True,
    )

    # ผู้ทำรายการโอน
    transfer_user_id = fields.Many2one(
        'res.users',
        string='ผู้ทำรายการโอน',
        copy=False,
        readonly=True,
    )

    def action_mark_transferred(self):
        """กดปุ่ม โอนแล้ว → เปลี่ยน state เป็น transferred"""
        for rec in self:
            if rec.state != 'posted':
                raise UserError(_('สามารถกดโอนแล้วได้เฉพาะเอกสารที่ Posted เท่านั้น'))
            rec.write({
                'state': 'transferred',
                'is_transferred': True,
                'transfer_status': 'transferred',
                'transfer_date': fields.Datetime.now(),
                'transfer_user_id': self.env.uid,
            })
        return True

    def action_unmark_transferred(self):
        """ย้อนกลับจาก transferred → posted"""
        for rec in self:
            if rec.state != 'transferred':
                raise UserError(_('สามารถยกเลิกโอนได้เฉพาะเอกสารที่โอนแล้วเท่านั้น'))
            rec.write({
                'state': 'posted',
                'is_transferred': False,
                'transfer_status': 'not_transferred',
                'transfer_date': False,
                'transfer_user_id': False,
            })
        return True
