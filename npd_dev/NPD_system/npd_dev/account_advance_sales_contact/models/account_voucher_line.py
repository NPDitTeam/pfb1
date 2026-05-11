# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountVoucherLine(models.Model):
    _inherit = 'account.voucher.line'

    sales_contact_id = fields.Many2one(
        'res.users',
        string='Sales ที่ติดต่อ',
        tracking=True,
        copy=True,
        help='Sales ที่ติดต่อลูกค้า ดึงมาจาก Sale Order',
        domain="[('employee_ids.department_id.name', 'ilike', 'Sales')]"
    )

    payment_date = fields.Date(
        string='วันที่กำหนดจ่าย',
        tracking=True,
        copy=True,
        help='วันที่กำหนดจ่ายเงินสำหรับรายการนี้',
    )

    def write(self, vals):
        """Override write เพื่อให้สามารถแก้ไข sales_contact_id และ payment_date ได้แม้ state = posted"""
        allowed_fields = {'sales_contact_id', 'payment_date'}

        # ตรวจสอบว่ามีแต่ฟิลด์ที่อนุญาตให้แก้เท่านั้น
        if set(vals.keys()).issubset(allowed_fields) and vals:
            allowed_vals = {k: v for k, v in vals.items() if k in allowed_fields}
            # ใช้ with_context เพื่อป้องกัน recursion
            if not self.env.context.get('_bypass_voucher_line_write'):
                return super(AccountVoucherLine, self.sudo().with_context(_bypass_voucher_line_write=True)).write(allowed_vals)
        return super(AccountVoucherLine, self).write(vals)


class AccountVoucher(models.Model):
    _inherit = 'account.voucher'

    def action_edit_sales_contact(self):
        """เปิด wizard สำหรับแก้ไข Sales Contact และ วันที่กำหนดจ่าย"""
        self.ensure_one()
        return {
            'name': 'แก้ไข Sales และ วันที่กำหนดจ่าย',
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.edit.sales.contact',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_voucher_id': self.id,
            },
        }