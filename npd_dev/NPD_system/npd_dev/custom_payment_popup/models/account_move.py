from odoo import models, fields, api
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_open_payment_popup(self):
        self.ensure_one()

        if self.state != 'posted':
            raise UserError("ใบแจ้งหนี้ต้องอยู่ในสถานะ 'ยืนยัน' ก่อนจึงจะสามารถชำระได้")

        # ✅ เช็คว่าเป็นใบลดหนี้หรือไม่ แล้วเลือก Journal ที่เหมาะสม
        if self.move_type == 'out_refund':
            # ใบลดหนี้ลูกค้า → ใช้สมุดรายวันรับชำระลดหนี้
            journal_name = 'สมุดรายวันรับชำระลดหนี้'
        else:
            # ใบแจ้งหนี้ปกติ → ใช้สมุดรายวันรับชำระ
            journal_name = 'สมุดรายวันรับชำระ'

        # ✅ ค้นหา Journal ที่ต้องการ
        journal = self.env['account.journal'].search([
            ('type', '=', 'receivable'),
            ('name', '=', journal_name)
        ], limit=1)

        if not journal:
            raise UserError("❌ ไม่พบ %s กรุณาตรวจสอบในเมนูบัญชี > สมุดรายวัน" % journal_name)

        return {
            'name': 'ชำระเงิน',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_payment_type': 'inbound',
                'default_partner_type': 'customer',
                'default_partner_id': self.partner_id.id,
                'default_date': self.invoice_date or fields.Date.today(),
                'default_communication': self.name,
                'default_search_invoice_name': self.name,
                'default_journal_id': journal.id,  # ✅ บังคับเลือกสมุดรายวัน
            }
        }
