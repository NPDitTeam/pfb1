from odoo import models, fields, api
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    def use_wht_billing_sheet_invoice(self):
        """ใบสั่งขายต้นทางของใบแจ้งหนี้นี้ ติ๊ก
           'ใช้ภาษีหัก ณ ที่จ่ายใบแจ้งหนี้/ใบวางบิล หัก 5%' ไว้หรือไม่

           ฟิลด์ use_wht_billing_sheet นิยามอยู่ในโมดูล custom_invoice_date
           ซึ่งบางฐานข้อมูลไม่ได้ติดตั้ง ถ้าไม่มีฟิลด์ให้ถือว่าไม่ติ๊ก
           ใบแจ้งหนี้ที่ไม่ได้ออกจากใบสั่งขายก็ถือว่าไม่ติ๊กเช่นกัน
           ถ้าใบแจ้งหนี้รวมหลายใบสั่งขาย ติ๊กใบใดใบหนึ่งก็ถือว่าหัก 5%"""
        return any(getattr(order, 'use_wht_billing_sheet', False)
                   for order in self.line_ids.sale_line_ids.order_id)

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

        # ✅ ตั้งค่าเริ่มต้นตามการติ๊กภาษีหัก ณ ที่จ่ายบนใบสั่งขาย
        #    ติ๊ก = ใบวางบิลหัก 5% ให้แล้ว -> หมายเหตุ "โอนเงินแบบหัก 5%" และติ๊ก Payment Multi ให้
        #    ไม่ติ๊ก = ยอดเต็ม -> หมายเหตุ "โอนเงินแบบหัก 7%"
        wht_5_percent = self.use_wht_billing_sheet_invoice()

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
                'default_note': 'โอนเงินแบบหัก 5%' if wht_5_percent else 'โอนเงินแบบหัก 7%',
                'default_is_payment_multi': wht_5_percent,
            }
        }
