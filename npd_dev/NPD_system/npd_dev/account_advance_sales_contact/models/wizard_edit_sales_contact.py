# -*- coding: utf-8 -*-
from odoo import models, fields, api


class WizardEditSalesContact(models.TransientModel):
    _name = 'wizard.edit.sales.contact'
    _description = 'Wizard Edit Sales Contact and Payment Date'

    voucher_id = fields.Many2one('account.voucher', string='Voucher', required=True)
    line_ids = fields.One2many('wizard.edit.sales.contact.line', 'wizard_id', string='Lines')

    @api.model
    def default_get(self, fields_list):
        res = super(WizardEditSalesContact, self).default_get(fields_list)
        voucher_id = self.env.context.get('default_voucher_id')
        if voucher_id:
            voucher = self.env['account.voucher'].browse(voucher_id)
            lines = []
            for line in voucher.line_ids:
                lines.append((0, 0, {
                    'voucher_line_id': line.id,
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'sales_contact_id': line.sales_contact_id.id,
                    'payment_date': line.payment_date,  # เพิ่มการดึงค่าวันที่
                }))
            res['line_ids'] = lines
        return res

    def action_confirm(self):
        """บันทึกการแก้ไข Sales Contact และ Payment Date"""
        for wizard_line in self.line_ids:
            if wizard_line.voucher_line_id:
                # ใช้ SQL update โดยตรงเพื่อ bypass ORM readonly พร้อมอัปเดต payment_date
                self.env.cr.execute("""
                    UPDATE account_voucher_line 
                    SET sales_contact_id = %s, payment_date = %s
                    WHERE id = %s
                """, (
                    wizard_line.sales_contact_id.id if wizard_line.sales_contact_id else None,
                    wizard_line.payment_date if wizard_line.payment_date else None,
                    wizard_line.voucher_line_id.id
                ))

        self.env.cr.commit()
        return {'type': 'ir.actions.act_window_close'}


class WizardEditSalesContactLine(models.TransientModel):
    _name = 'wizard.edit.sales.contact.line'
    _description = 'Wizard Edit Sales Contact Line'

    wizard_id = fields.Many2one('wizard.edit.sales.contact', string='Wizard', required=True, ondelete='cascade')
    voucher_line_id = fields.Many2one('account.voucher.line', string='Voucher Line')
    product_id = fields.Many2one('product.product', string='สินค้า', readonly=True)
    name = fields.Char(string='รายละเอียด', readonly=True)
    sales_contact_id = fields.Many2one(
        'res.users',
        string='Sales ที่ติดต่อ',
        domain="[('employee_ids.department_id.name', 'ilike', 'Sales')]"
    )
    # เพิ่มฟิลด์สำหรับรับค่า วันที่กำหนดจ่าย ใน Wizard
    payment_date = fields.Date(string='วันที่กำหนดจ่าย')