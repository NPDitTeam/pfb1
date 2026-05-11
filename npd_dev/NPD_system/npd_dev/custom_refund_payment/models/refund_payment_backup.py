from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date

class FleetChatterService(models.Model):
    _name = 'fleet.refund.service'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def log_note_action(self):
        # ฟังก์ชันการโพสต์ข้อความลงใน Chatter
        self.message_post(body="นี่คือบันทึกการติดตามสำหรับบริการ Fleet Chatter")

    @api.model
    def schedule_activity_action(self):
        # การตั้งกิจกรรมที่ต้องติดตาม
        activity_type = self.env.ref('mail.mail_activity_data_todo')  # กิจกรรมที่ต้องทำ
        self.activity_schedule(activity_type.id, 'ติดตามบริการ Fleet Chatter')  # กำหนดชื่อกิจกรรมเป็นภาษาไทย


class refundPayment(models.Model):
    _name = 'refund.payment'
    _description = 'Refund Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    date = fields.Date(
        string='วันที่',
        default=lambda self: date.today(),  # ✅ เรียกวันปัจจุบันแบบไม่ Error
        required=True,  # ❗️บังคับกรอก
        tracking=True  # 📌 ติดตามใน Chatter
    )

    transfer_type = fields.Selection([
        ('overpaid_refund', 'คืนเงินโอนเกิน'),
        ('wtax_refund', 'คืนหัก ณ ที่จ่าย'),
        ('rental_difference', 'โอนคืนค่าเช่าส่วนต่าง'),
    ], string='ประเภทการโอน', required=True, default='')

    show_fleet_refund_button = fields.Boolean(string='Show Fleet Refund Button', compute='_compute_show_fleet_refund_button')
    show_state = fields.Boolean(string='Show state', default=False)


    name = fields.Char(string='เลขเอกสาร', required=True, default='New', tracking=True,readonly=True)
    state = fields.Selection([
        ('draft', 'ร่าง'),
        ('confirmed', 'ยืนยันแล้ว')],
        string='สถานะ', default='draft', tracking=True)
    branch_id = fields.Many2one(
        'res.branch',
        string="สาขา",
        default=lambda self: self.env.user.branch_id.id,
        readonly=True
    )
    move_id = fields.Many2one('account.move', string='รายการบันทึกบัญชี', readonly=True)

    payment_ids = fields.Many2many(
        'account.payment',
        string='เลือกการชำระเงิน',
        domain=[],  # จะควบคุมผ่าน @api.onchange
    )

    payment_lines = fields.One2many(
        'refund.payment.line',
        'refund_payment_id',
        string='รายการชำระเงิน'
    )

    @api.onchange('transfer_type')
    def _onchange_transfer_type_domain(self):
        for rec in self:
            domain = [
                ('payment_type', '=', 'inbound'),
                ('branch_id', '=', rec.branch_id.id)
            ]

            if rec.transfer_type == 'overpaid_refund':
                domain += [('overpaid_refund_status', '=', False)]
            elif rec.transfer_type == 'wtax_refund':
                domain += [('wtax_refund_status', '=', False)]
            elif rec.transfer_type == 'rental_difference':
                domain += [('rental_difference_status', '=', False)]

            return {
                'domain': {
                    'payment_ids': domain
                }
            }


    @api.depends('create_uid')
    def _compute_show_fleet_refund_button(self):
        for rec in self:
            rec.show_fleet_refund_button = rec.env.user.fleet_refund

    def show_overpaid_reverse_button(self):
        for rec in self:
            rec.show_reverse_button = rec.transfer_type == 'overpaid_refund'

    show_reverse_button = fields.Boolean(
        string='Show Reverse Button', compute='show_overpaid_reverse_button'
    )

    def action_reset_to_draft(self):
        for rec in self:
            # ✅ ยกเลิกรายการบัญชี ถ้ามี
            if rec.move_id:
                if rec.move_id.state == 'posted':
                    try:
                        rec.move_id.button_draft()  # เปลี่ยนสถานะเป็น draft
                    except Exception as e:
                        raise UserError(_("ไม่สามารถเปลี่ยนสถานะเอกสารบัญชีให้เป็นร่างได้: %s" % str(e)))
                # ❌ อย่าลบ rec.move_id.unlink()

            # ✅ กลับเป็นร่าง
            rec.state = 'draft'
            rec.show_state = False
            # ✅ รีเซ็ตสถานะเงินสด
            for p in rec.payment_ids:
                if rec.transfer_type =='overpaid_refund':
                    p.overpaid_refund_status = ''

                elif rec.transfer_type =='wtax_refund':
                    p.wtax_refund_status = ''

                elif rec.transfer_type =='rental_difference':
                    p.rental_difference_status = ''

                # ถ้ามี refund_invoice_id: p.refund_invoice_id = False

            # ✅ แจ้งเตือนข้อความ
            rec.message_post(body='ยกเลิกรายการและกลับเป็นฉบับร่างเรียบร้อยแล้ว')

    @api.onchange('payment_ids')
    def _onchange_payment_ids(self):
        self.payment_lines = [(5, 0, 0)]
        line_vals = []
        for p in self.payment_ids:
            line_vals.append((0, 0, {
                'payment_name': p.name,
                'payment_id': p.id,
                'partner_id': p.partner_id.id,

                'payment_date': p.date,
            }))
        self.payment_lines = line_vals

    def action_reverse_overpaid(self):
        for rec in self:
            if rec.transfer_type != 'overpaid_refund':
                raise UserError("ปุ่มนี้ใช้ได้เฉพาะกรณีคืนเงินโอนเกินเท่านั้น")
            if rec.state != 'confirmed':
                raise UserError("สามารถกลับขาบัญชีได้เมื่อเอกสารอยู่ในสถานะ Confirmed เท่านั้น")

            # journal = self.env['account.journal'].search([], limit=1)
            journal = self.env['account.journal'].search([
                ('name', '=', 'สมุดรายวันเช่า(สาขา)')
            ], limit=1)
            debit_account = self.env['account.account'].search([('code', '=', '1112-01')], limit=1)
            credit_account = self.env['account.account'].search([('code', '=', '9999-99')], limit=1)

            if not debit_account or not credit_account:
                raise UserError("ไม่พบบัญชีที่ต้องการกลับขา")

            lines = []
            for line in rec.payment_lines:
                lines.append((0, 0, {
                    'account_id': debit_account.id,
                    'name': f'REVERSE: {line.payment_name}',
                    'debit': 0,
                    'credit': line.amount,
                    'partner_id': line.partner_id.id,
                    'branch_id': rec.branch_id.id,
                }))
                lines.append((0, 0, {
                    'account_id': credit_account.id,
                    'name': f'REVERSE: {line.payment_name}',
                    'debit': line.amount,
                    'credit': 0,
                    'partner_id': line.partner_id.id,
                    'branch_id': rec.branch_id.id,
                }))

            move = self.env['account.move'].create({
                'journal_id': journal.id,
                'date': fields.Date.today(),
                'ref': rec.name + '-REVERSE',
                'line_ids': lines,
                'branch_id': rec.branch_id.id,
            })
            move._post()

            # ✅ บันทึก journal entry กลับขา
            rec.move_id = move.id

            rec.message_post(body='กลับขาบัญชีสำเร็จ: %s' % move.name)
            rec.show_state =  True
            if rec.transfer_type == 'overpaid_refund':
                for p in rec.payment_ids:
                    p.overpaid_refund_status = 'overpaid_refund'


    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                continue

                # ✅ ตรวจสอบว่าทุกบรรทัดมีค่า amount มากกว่า 0
            for line in rec.payment_lines:
                if not line.amount or line.amount == 0.0:
                    raise UserError(_("กรุณาระบุจำนวนเงิน ให้มากกว่า 0 ในรายการ: %s" % line.payment_name))

            if not rec.name or rec.name in ['New', '/']:
                    rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=fields.Date.today()).next_by_code('overpaid_refund.payment') or '/'


            # journal = self.env['account.journal'].search([], limit=1)

            journal = self.env['account.journal'].search([
                ('name', '=', 'สมุดรายวันเช่า(สาขา)')
            ], limit=1)

            if not journal:
                raise UserError("ไม่พบสมุดรายวัน กรุณาสร้างอย่างน้อย 1 รายการ")

            lines = []

            if rec.transfer_type == 'overpaid_refund':
                debit_account = self.env['account.account'].search([('code', '=', '9999-99')], limit=1)
                credit_account = self.env['account.account'].search([('code', '=', '1113-01')], limit=1)
            elif rec.transfer_type == 'wtax_refund':
                debit_account = self.env['account.account'].search([('code', '=', '1151-02')], limit=1)
                credit_account = self.env['account.account'].search([('code', '=', '1113-01')], limit=1)

            elif rec.transfer_type == 'rental_difference':
                debit_account = self.env['account.account'].search([('code', '=', '4100-01')], limit=1)
                credit_account = self.env['account.account'].search([('code', '=', '1113-01')], limit=1)

            else:
                raise UserError("กรุณาเลือกประเภทการโอน")

            if not debit_account or not credit_account:
                raise UserError("รหัสบัญชีที่เกี่ยวข้องไม่พบในระบบ")
            if rec.transfer_type == 'overpaid_refund':
                for line in rec.payment_lines:
                    lines.append((0, 0, {
                        'account_id': debit_account.id,
                        'name': f'Refund: {line.payment_name}',
                        'debit': 0,
                        'credit': line.amount,
                        'partner_id': line.partner_id.id,
                        'branch_id': rec.branch_id.id,
                    }))
                    lines.append((0, 0, {
                        'account_id': credit_account.id,
                        'name': f'Refund: {line.payment_name}',
                        'debit': line.amount,
                        'credit': 0,
                        'partner_id': line.partner_id.id,
                        'branch_id': rec.branch_id.id,
                    }))
            if rec.transfer_type == 'wtax_refund':
                for line in rec.payment_lines:
                    lines.append((0, 0, {
                        'account_id': debit_account.id,
                        'name': f'Refund: {line.payment_name}',
                        'debit': line.amount,
                        'credit': 0,
                        'partner_id': line.partner_id.id,
                        'branch_id': rec.branch_id.id,
                    }))
                    lines.append((0, 0, {
                        'account_id': credit_account.id,
                        'name': f'Refund: {line.payment_name}',
                        'debit': 0,
                        'credit': line.amount,
                        'partner_id': line.partner_id.id,
                        'branch_id': rec.branch_id.id,
                    }))
            if rec.transfer_type == 'rental_difference':
                for line in rec.payment_lines:
                    lines.append((0, 0, {
                        'account_id': debit_account.id,
                        'name': f'Refund: {line.payment_name}',
                        'debit': line.amount,
                        'credit': 0,
                        'partner_id': line.partner_id.id,
                        'branch_id': rec.branch_id.id,
                    }))
                    lines.append((0, 0, {
                        'account_id': credit_account.id,
                        'name': f'Refund: {line.payment_name}',
                        'debit': 0,
                        'credit': line.amount,
                        'partner_id': line.partner_id.id,
                        'branch_id': rec.branch_id.id,
                    }))

            move = self.env['account.move'].create({
                'journal_id': journal.id,
                'date': fields.Date.today(),
                'ref': rec.name,
                'line_ids': lines,
                'branch_id': rec.branch_id.id,
            })
            move._post()
            rec.move_id = move.id
            rec.state = 'confirmed'
            rec.message_post(body='บันทึกบัญชีสำเร็จ: %s' % move.name)

            # ✅ กรณี "คืนหัก ณ ที่จ่าย" อัปเดตสถานะ payment
            if rec.transfer_type == 'wtax_refund':
                rec.show_state = True
                for p in rec.payment_ids:
                    p.wtax_refund_status = 'wtax_refund'

            if rec.transfer_type == 'rental_difference':
                rec.show_state = True
                for p in rec.payment_ids:
                    p.rental_difference_status = 'rental_difference'

class refundPaymentLine(models.Model):
    _name = 'refund.payment.line'
    _description = 'Refund Payment Detail Line'

    refund_payment_id = fields.Many2one('refund.payment', string='การคืนเงิน')
    payment_name = fields.Char(string='รหัสการชำระเงิน')
    payment_id = fields.Many2one('account.payment', string='รายการชำระเงิน')
    partner_id = fields.Many2one('res.partner', string='ลูกค้า')
    amount = fields.Float(string='จำนวนเงิน', required=True)
    payment_date = fields.Date(string='วันที่ชำระเงิน')

