# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    # override เฉพาะ attribute required — attribute อื่น (comodel/string/help)
    # ยังใช้ค่าเดิมจากโมดูล npd_analytic_branch
    branch_id = fields.Many2one(required=True)

    @api.constrains('branch_id')
    def _check_branch_required(self):
        """กันทุกช่องทาง (UI + create/write จากโค้ด) ให้ต้องมีสาขาเสมอ"""
        for rec in self:
            if not rec.branch_id:
                raise ValidationError(_(
                    'กรุณาเลือก "สาขา" สำหรับบัญชีวิเคราะห์ "%s" '
                    'ก่อนบันทึก'
                ) % (rec.name or ''))
