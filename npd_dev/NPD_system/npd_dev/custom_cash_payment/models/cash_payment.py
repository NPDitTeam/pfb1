from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FleetChatterService(models.Model):
    _name = 'fleet.chatter.service'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def log_note_action(self):
        self.message_post(body="นี่คือบันทึกการติดตามสำหรับบริการ Fleet Chatter")

    @api.model
    def schedule_activity_action(self):
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        self.activity_schedule(activity_type.id, 'ติดตามบริการ Fleet Chatter')


class CashPayment(models.Model):
    _name = 'cash.payment'
    _description = 'Cash Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # name = fields.Char(string='Reference', required=True, default='New', tracking=True, readonly=True)
    name = fields.Char(
        string='Reference',
        required=True,
        default='New',
        tracking=True,
        readonly=True,  # ← เปลี่ยนเป็นนี้
        states={'draft': [('readonly', False)]}  # ← ให้แก้ไขได้ตอน draft
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed')],
        string='Status', default='draft', tracking=True)
    branch_id = fields.Many2one(
        'res.branch',
        string="Branch",
        default=lambda self: self.env.user.branch_id.id,
        readonly=True
    )
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)

    payment_ids = fields.Many2many(
        'account.payment',
        string='Payments',
        domain="[('payment_method_one_id.name', '=', 'เงินสด'),"
               " ('payment_type', '=', 'inbound'),"
               " ('branch_id', '=', branch_id),"
               " ('cash_status', '=', False)]"
    )

    payment_lines = fields.One2many(
        'cash.payment.line',
        'cash_payment_id',
        string='รายการชำระเงิน'
    )

    date_created = fields.Date(
        string='วันที่สร้างเอกสาร',
        default=fields.Date.today,
        # readonly=True,
        tracking=True
    )

    total_amount = fields.Float(
        string='ยอดรวม',
        compute='_compute_total_amount',
        store=True,
        tracking=True
    )

    def copy(self, default=None):
        raise UserError(_("ไม่อนุญาตให้ทำรายการซ้ำ (Duplicate) สำหรับเอกสารนี้"))

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("ห้ามลบเอกสารเมื่อไม่ใช่ Draft"))
        return super(CashPayment, self).unlink()

    @api.depends('payment_lines.amount')
    def _compute_total_amount(self):
        """คำนวณยอดรวมจากทุกรายการใน payment_lines"""
        for record in self:
            record.total_amount = sum(record.payment_lines.mapped('amount'))

    # def action_reset_to_draft(self):
    #     for rec in self:
    #         # ยกเลิกรายการบัญชี ถ้ามี
    #         if rec.move_id:
    #             if rec.move_id.state == 'posted':
    #                 try:
    #                     rec.move_id.button_draft()
    #                 except Exception as e:
    #                     raise UserError(_("ไม่สามารถเปลี่ยนสถานะเอกสารบัญชีให้เป็นร่างได้: %s" % str(e)))
    #
    #         # กลับเป็นร่าง
    #         rec.state = 'draft'
    #
    #         # รีเซ็ตสถานะเงินสด
    #         for p in rec.payment_ids:
    #             p.cash_status = ''
    #             # ถ้ามี field cash_invoice_id ให้รีเซ็ต
    #             if hasattr(p, 'cash_invoice_id'):
    #                 p.cash_invoice_id = False
    #
    #         # แจ้งเตือนข้อความ
    #         rec.message_post(body='ยกเลิกรายการและกลับเป็นฉบับร่างเรียบร้อยแล้ว')

    def action_reset_to_draft(self):
        for rec in self:
            # ยกเลิกรายการบัญชี ถ้ามี
            if rec.move_id:
                try:
                    if rec.move_id.state == 'posted':
                        # ย้อนกลับ journal entry เป็น draft
                        rec.move_id.button_draft()
                    # เก็บไว้แบบ draft เพื่อตรวจสอบ ไม่ลบ
                except Exception as e:
                    raise UserError(_("ไม่สามารถเปลี่ยนสถานะเอกสารบัญชีให้เป็นร่างได้: %s" % str(e)))

            # กลับเป็นร่าง
            rec.state = 'draft'

            # รีเซ็ตสถานะเงินสด
            for p in rec.payment_ids:
                p.cash_status = ''
                # ถ้ามี field cash_invoice_id ให้รีเซ็ต
                if hasattr(p, 'cash_invoice_id'):
                    p.cash_invoice_id = False

            # แจ้งเตือนข้อความ
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
                'amount': p.amount,
                'payment_date': p.date,
            }))
        self.payment_lines = line_vals

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                continue

            # ตรวจสอบว่ามี payment lines หรือไม่
            if not rec.payment_lines:
                raise UserError(_("กรุณาเลือกรายการชำระเงินอย่างน้อย 1 รายการ"))

            # ให้ ORM สร้าง sequence number ถ้ายังไม่มี
            if rec.name in ['New', '/']:
                # ใช้ write เพื่อให้ default_get ทำงาน
                rec.name = self.env['ir.sequence'].next_by_code('cash.payment') or f"CP/{fields.Date.today().year}/0001"

            # ค้นหาบัญชี
            cash_account = self.env['account.account'].search([('code', '=', '1111-00')], limit=1)
            ar_account = self.env['account.account'].search([('code', '=', '1113-01')], limit=1)

            if not cash_account or not ar_account:
                raise UserError(_("กรุณาตั้งค่าบัญชี 1111-00 หรือ 1113-01 ให้เรียบร้อยก่อน"))

            # ค้นหา journal
            journal = self.env['account.journal'].search([('type', '=', 'cash')], limit=1)
            if not journal:
                raise UserError(_("ไม่พบสมุดรายวันประเภทเงินสด กรุณาสร้างหรือเปิดใช้งาน"))

            # สร้างบรรทัดรายการบัญชี
            lines = []
            total_amount = 0

            for line in rec.payment_lines:
                # Credit เงินสด
                lines.append((0, 0, {
                    'account_id': cash_account.id,
                    'name': 'Cash Payment: ' + (line.payment_name or ''),
                    'credit': line.amount,
                    'debit': 0,
                    'partner_id': line.partner_id.id if line.partner_id else False,
                    'branch_id': rec.branch_id.id if rec.branch_id else False,
                }))

                # Debit AR
                lines.append((0, 0, {
                    'account_id': ar_account.id,
                    'name': 'Receive: ' + (line.payment_name or ''),
                    'debit': line.amount,
                    'credit': 0,
                    'partner_id': line.partner_id.id if line.partner_id else False,
                    'branch_id': rec.branch_id.id if rec.branch_id else False,
                }))

                total_amount += line.amount

            # ตรวจสอบว่ามีรายการบัญชีหรือไม่
            if not lines:
                raise UserError(_("ไม่สามารถสร้างรายการบัญชีได้ กรุณาตรวจสอบข้อมูล"))

            # สร้างรายการบัญชี
            move_vals = {
                'journal_id': journal.id,
                'date': fields.Date.today(),
                'ref': rec.name,
                'line_ids': lines,
            }

            # เพิ่ม branch_id ถ้ามี
            if rec.branch_id:
                move_vals['branch_id'] = rec.branch_id.id

            move = self.env['account.move'].create(move_vals)

            # Post รายการบัญชี
            move._post()
            rec.move_id = move.id

            # อัปเดทสถานะ payment
            for p in rec.payment_ids:
                # Post payment ถ้ายังเป็น draft
                if p.state == 'draft':
                    try:
                        p.action_post()
                    except Exception as e:
                        # Log error แต่ไม่หยุดการทำงาน
                        rec.message_post(body='Warning: ไม่สามารถ post payment %s: %s' % (p.name, str(e)))

                # อัปเดท cash_status
                p.cash_status = 'returned'

                # อัปเดท cash_invoice_id ถ้ามี reconciled invoice
                if hasattr(p, 'cash_invoice_id'):
                    if p.reconciled_invoice_ids:
                        # ตรวจสอบว่ามี invoice ที่ reconcile หรือไม่
                        p.cash_invoice_id = p.reconciled_invoice_ids[0].id
                    else:
                        # ถ้าไม่มี invoice ที่ reconcile ให้ log warning
                        rec.message_post(
                            body='Warning: Payment %s ไม่มี invoice ที่ reconcile' % p.name
                        )

            # อัปเดทสถานะเป็น confirmed
            rec.state = 'confirmed'

            # Post message
            rec.message_post(
                body='ยืนยันการชำระเงินและสร้างรายการบัญชีสำเร็จ: %s (จำนวน %.2f บาท)' % (move.name, total_amount)
            )

    # def action_confirm(self):
    #     for rec in self:
    #         if rec.state != 'draft':
    #             continue
    #
    #         # ตรวจสอบว่ามี payment lines หรือไม่
    #         if not rec.payment_lines:
    #             raise UserError(_("กรุณาเลือกรายการชำระเงินอย่างน้อย 1 รายการ"))
    #
    #         # รันเลขเอกสารแค่ครั้งเดียว ถ้ายังเป็นค่า default
    #         if not rec.name or rec.name in ['New', '/']:
    #             rec.name = self.env['ir.sequence'].next_by_code('cash.payment') or '/'
    #
    #         # ค้นหาบัญชี
    #         cash_account = self.env['account.account'].search([('code', '=', '1111-00')], limit=1)
    #         ar_account = self.env['account.account'].search([('code', '=', '1113-01')], limit=1)
    #
    #         if not cash_account or not ar_account:
    #             raise UserError(_("กรุณาตั้งค่าบัญชี 1111-00 หรือ 1113-01 ให้เรียบร้อยก่อน"))
    #
    #         # ค้นหา journal
    #         journal = self.env['account.journal'].search([('type', '=', 'cash')], limit=1)
    #         if not journal:
    #             raise UserError(_("ไม่พบสมุดรายวันประเภทเงินสด กรุณาสร้างหรือเปิดใช้งาน"))
    #
    #         # สร้างบรรทัดรายการบัญชี
    #         lines = []
    #         total_amount = 0
    #
    #         for line in rec.payment_lines:
    #             # Credit เงินสด
    #             lines.append((0, 0, {
    #                 'account_id': cash_account.id,
    #                 'name': 'Cash Payment: ' + (line.payment_name or ''),
    #                 'credit': line.amount,
    #                 'debit': 0,
    #                 'partner_id': line.partner_id.id if line.partner_id else False,
    #                 'branch_id': rec.branch_id.id if rec.branch_id else False,
    #             }))
    #
    #             # Debit AR
    #             lines.append((0, 0, {
    #                 'account_id': ar_account.id,
    #                 'name': 'Receive: ' + (line.payment_name or ''),
    #                 'debit': line.amount,
    #                 'credit': 0,
    #                 'partner_id': line.partner_id.id if line.partner_id else False,
    #                 'branch_id': rec.branch_id.id if rec.branch_id else False,
    #             }))
    #
    #             total_amount += line.amount
    #
    #         # ตรวจสอบว่ามีรายการบัญชีหรือไม่
    #         if not lines:
    #             raise UserError(_("ไม่สามารถสร้างรายการบัญชีได้ กรุณาตรวจสอบข้อมูล"))
    #
    #         # สร้างรายการบัญชี
    #         move_vals = {
    #             'journal_id': journal.id,
    #             'date': fields.Date.today(),
    #             'ref': rec.name,
    #             'line_ids': lines,
    #         }
    #
    #         # เพิ่ม branch_id ถ้ามี
    #         if rec.branch_id:
    #             move_vals['branch_id'] = rec.branch_id.id
    #
    #         move = self.env['account.move'].create(move_vals)
    #
    #         # Post รายการบัญชี
    #         move._post()
    #         rec.move_id = move.id
    #
    #         # อัปเดทสถานะ payment
    #         for p in rec.payment_ids:
    #             # Post payment ถ้ายังเป็น draft
    #             if p.state == 'draft':
    #                 try:
    #                     p.action_post()
    #                 except Exception as e:
    #                     # Log error แต่ไม่หยุดการทำงาน
    #                     rec.message_post(body='Warning: ไม่สามารถ post payment %s: %s' % (p.name, str(e)))
    #
    #             # อัปเดท cash_status
    #             p.cash_status = 'returned'
    #
    #             # อัปเดท cash_invoice_id ถ้ามี reconciled invoice
    #             if hasattr(p, 'cash_invoice_id'):
    #                 if p.reconciled_invoice_ids:
    #                     # ตรวจสอบว่ามี invoice ที่ reconcile หรือไม่
    #                     p.cash_invoice_id = p.reconciled_invoice_ids[0].id
    #                 else:
    #                     # ถ้าไม่มี invoice ที่ reconcile ให้ log warning
    #                     rec.message_post(
    #                         body='Warning: Payment %s ไม่มี invoice ที่ reconcile' % p.name
    #                     )
    #
    #         # อัปเดทสถานะเป็น confirmed
    #         rec.state = 'confirmed'
    #
    #         # Post message
    #         rec.message_post(
    #             body='ยืนยันการชำระเงินและสร้างรายการบัญชีสำเร็จ: %s (จำนวน %.2f บาท)' % (move.name, total_amount)
    #         )


class CashPaymentLine(models.Model):
    _name = 'cash.payment.line'
    _description = 'Cash Payment Detail Line'

    cash_payment_id = fields.Many2one('cash.payment', string='Cash Payment', ondelete='cascade')
    payment_name = fields.Char(string='Payment Name')
    payment_id = fields.Many2one('account.payment', string='Payment')
    partner_id = fields.Many2one('res.partner', string='Customer')
    amount = fields.Float(string='Amount')
    payment_date = fields.Date(string='Payment Date')