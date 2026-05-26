# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

_logger = logging.getLogger(__name__)


# ✅ กัน OSError [Errno 22] Invalid argument บน Windows (รัน Odoo เป็น service → stdout ใช้ไม่ได้)
#    redirect print(...) ทั้งไฟล์ไปที่ logger.debug แทนการเขียน stdout โดยตรง (ข้อความ debug ไม่หาย/ไม่ crash)
def print(*args, **kwargs):
    try:
        _logger.debug(' '.join(str(a) for a in args))
    except Exception:
        pass


class AccountVoucher(models.Model):
    _name = 'account.voucher'
    _description = 'Accounting Voucher'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date desc, id desc"

    def _default_journal(self):
        voucher_type = self._context.get('voucher_type') == 'sale' and 'receivable' or 'payable'
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', '=', voucher_type),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)

    def _default_payment_journal(self):
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', ('bank', 'cash')),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)

    voucher_type = fields.Selection([
        ('sale', 'Sale'),
        ('purchase', 'Purchase')
    ], string='Type', readonly=True, states={'draft': [('readonly', False)]}, oldname="type")
    name = fields.Char('Payment Memo',
                       readonly=True, states={'draft': [('readonly', False)]}, copy=False)
    date = fields.Date("Bill Date", readonly=True, required=True,
                       index=True, states={'draft': [('readonly', False)]},
                       copy=False, default=fields.Date.context_today)
    account_date = fields.Date("Accounting Date",
                               readonly=True, index=True, states={'draft': [('readonly', False)]},
                               help="Effective date for accounting entries", copy=False,
                               default=fields.Date.context_today)
    journal_id = fields.Many2one('account.journal', 'Journal',
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 default=_default_journal)
    payment_journal_id = fields.Many2one('account.journal', string='Payment Method', readonly=True,
                                         states={'draft': [('readonly', False)]},
                                         domain="[('type', 'in', ['cash', 'bank'])]", default=_default_payment_journal)
    account_id = fields.Many2one('account.account', 'Account',
                                 required=False, readonly=True, states={'draft': [('readonly', False)]},
                                 domain="[('deprecated', '=', False), ('internal_type','=', (voucher_type == 'purchase' and 'payable' or 'receivable'))]")
    line_ids = fields.One2many('account.voucher.line', 'voucher_id', 'Voucher Lines',
                               readonly=True, copy=True,
                               states={'draft': [('readonly', False)]})
    narration = fields.Text('Notes', readonly=True, tracking=True, states={'draft': [('readonly', False)], 'posted': [('readonly', False)]})
    currency_id = fields.Many2one('res.currency', compute='_get_journal_currency',
                                  string='Currency', readonly=True, store=True,
                                  default=lambda self: self._get_currency())
    company_id = fields.Many2one('res.company', 'Company',
                                 store=True, readonly=True,
                                 default=lambda self: self._get_company())
    state = fields.Selection([
        ('draft', 'Draft'),
        ('paid', 'paid'),
        ('cancel', 'Cancelled'),
        ('proforma', 'Pro-forma'),
        ('posted', 'Posted')
    ], 'Status', readonly=True, copy=False, default='draft', tracking=True,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed Voucher.\n"
             " * The 'Pro-forma' status is used when the voucher does not have a voucher number.\n"
             " * The 'Posted' status is used when user create voucher,a voucher number is generated and voucher entries are created in account.\n"
             " * The 'Cancelled' status is used when user cancel voucher.")
    reference = fields.Char('Bill Reference', readonly=True, states={'draft': [('readonly', False)]},
                            help="The partner reference of this document.", copy=False)
    amount = fields.Monetary(string='Total', store=True, readonly=True, compute='_compute_total')
    tax_amount = fields.Monetary(readonly=True, store=True, compute='_compute_total')
    tax_correction = fields.Monetary(readonly=True, states={'draft': [('readonly', False)]},
                                     help='In case we have a rounding problem in the tax, use this field to correct it')
    number = fields.Char(readonly=True, copy=False)
    move_id = fields.Many2one('account.move', 'Journal Entry', copy=False)
    partner_id = fields.Many2one('res.partner', 'Partner', required=True, change_default=1, readonly=True,
                                 states={'draft': [('readonly', False)]})
    paid = fields.Boolean(compute='_check_paid', help="The Voucher has been totally paid.")
    pay_now = fields.Selection([
        ('pay_now', 'Pay Directly'),
        ('pay_later', 'Pay Later'),
    ], 'Payment', index=True, readonly=True, states={'draft': [('readonly', False)]}, default='pay_now')
    date_due = fields.Date('Due Date', readonly=True, index=True, states={'draft': [('readonly', False)]})
    payment_method_id = fields.Many2one('payment.method', string='Payment Method', required=False, tracking=True,
                                        domain="[('is_active','=',True),'|',('company_id', '=', False),('company_id', '=', company_id)]")
    cheque_id = fields.Many2one("account.cheque", string="Cheque",
                                domain="[('state', '=', 'draft')]")
    type = fields.Selection(
        'Payment method',
        related='payment_method_id.type',
        required=True
    )
    is_payment_multi = fields.Boolean(string='Payment Multi', default=False)
    wt_cert_ids = fields.One2many(
        comodel_name="withholding.tax.cert",
        inverse_name="voucher_id",
        string="Withholding Tax Cert.",
        readonly=False,
    )
    payment_ids = fields.One2many(comodel_name="account.voucher.payment", inverse_name="voucher_id", string="payment",
                                  required=False, )
    wht_amount = fields.Monetary(string='Withholding Tax Amount', store=True, readonly=True, compute='_compute_total')
    cheque_type = fields.Selection(
        [
            ("outbound", "Payment Cheque"),
            ("inbound", "Receipt Cheque"),
        ],
        string="Cheque Type",
        default="inbound",
        required=True,
    )
    tax_line = fields.One2many(comodel_name="account.move.tax.invoice", inverse_name="voucher_id", string="",
                               required=False, )
    old_move_name = fields.Char(
        string="Old Move name",
        required=False,
    )

    check_type_show = fields.Char('Check Type Show', readonly=True, store=True, compute="_compute_check_type")

    rental_return_select_id = fields.Many2one(
        'stock.picking',
        string='เลือกใบคืนการเช่า',
        domain="rental_return_domain",  # ใช้ domain แบบ dynamic
        help="เลือกใบคืนการเช่าที่เกี่ยวข้อง",
        store=True
    )

    # ฟิลด์อ้างอิงใบคืนการเช่า
    rental_return_id = fields.Many2one(
        'stock.picking',
        string='เลขใบคืนการเช่า',
        help="เลือกใบคืนการเช่าที่เกี่ยวข้อง", store=True, readonly=True
    )

    check_show = fields.Boolean(string="Check Show", default=False)  # รับค่าจาก context (default_check_show)
    check_type_show_selection = fields.Selection(
        [('true', 'True'), ('false', 'False')],
        string="Check Type Show",
        compute="_compute_check_type_show",
        store=True
    )
    no_deduction = fields.Boolean(string="ไม่หักค่าประกัน", default=True)

    invoice_ids = fields.Many2many(
        'account.move',
        string='หนี้ค้างชำระ',
        relation='voucher_move_rel_npd',
        column1='voucher_id',
        column2='move_id',
        domain=[],  # ← ปล่อยว่างไว้
    )

    # ✅ เปลี่ยนเป็น Many2many เพื่อเก็บ Invoice IDs ที่ valid
    available_invoice_ids = fields.Many2many(
        'account.move',
        string='Available Invoices',
        compute='_compute_available_invoice_ids',
        store=False,
    )
    total_outstanding = fields.Float(
        string='ยอดหนี้ค้างชำระรวม',
        compute='_compute_total_outstanding',
        store=True,
        digits=(12, 2)
    )

    # เพิ่มฟิลด์สำหรับเก็บ payment ที่สร้างจาก voucher
    payment_t_ids = fields.Many2many('account.payment', string="Payments")

    # ✅ ต้องเพิ่มฟิลด์นี้เข้าไปใน Model
    show_payment_button = fields.Boolean(
        compute='_compute_show_payment_button',
        store=False,
    )

    invoice_ref_ids = fields.Many2many(
        'account.move',
        string='อ้างอิงหนี้ค้างชำระ (ประวัติ)',
        help='บันทึกใบแจ้งหนี้ที่เคยถูกเลือกตอนกดรับชำระ เพื่ออ้างอิงภายหลัง',
        readonly=True
    )

    # reference_summary = fields.Text(
    #     string='สรุปการอ้างอิง',
    #     compute='_compute_reference_summary',
    #     store=False
    # )

    can_edit_lines = fields.Boolean(
        compute='_compute_can_edit_lines',
        store=False,
    )
    outstanding_amount_snapshot = fields.Float(
        string='ยอดค้างชำระรวมที่บันทึก',
        readonly=True,
        digits=(12, 2),
        copy=False,
    )

    # ✅ เพิ่มฟิลด์ใหม่ตรงนี้
    payment_ref_id = fields.Many2one(
        'account.payment',
        string='ใบรับชำระค่าประกัน',
        compute='_compute_payment_from_reference',
        store=True,
        help='ใบรับชำระแรกที่พบจาก Bill Reference'
    )

    rental_return_domain = fields.Char(
        compute='_compute_rental_return_domain',
        readonly=True,
        store=False,
    )

    @api.depends("check_show")
    def _compute_check_type_show(self):
        for record in self:
            print(f"\n[_compute_check_type_show] check_show = {record.check_show}")
            record.check_type_show_selection = 'true' if record.check_show else 'false'
            print(f"[_compute_check_type_show] check_type_show_selection = {record.check_type_show_selection}")

    @api.model
    def default_get(self, fields):
        """ดึงค่า `default_check_show` จาก context แล้วตั้งค่าให้ `check_show`"""
        res = super(AccountVoucher, self).default_get(fields)
        context_check_show = self.env.context.get('default_check_show', False)
        res['check_show'] = context_check_show
        print(f"\n[default_get] context default_check_show = {context_check_show}")
        print(f"[default_get] res['check_show'] = {res['check_show']}")
        return res

    @api.depends('partner_id', 'reference')
    def _compute_rental_return_domain(self):
        """คำนวณ domain สำหรับ rental_return_select_id แบบ dynamic"""
        for rec in self:
            domain = [
                ('deposit_return_state', '=', 'not_returned'),
                ('name', 'not ilike', '%OUT%')
            ]

            # กรองจาก reference ก่อนถ้ามี (ต้องเช็ค check_show ด้วย)
            if rec.reference and rec.check_show:
                # ✅ เช็ค sale.order.rental_status != 'done'
                sale_order = rec.env['sale.order'].search([
                    ('name', '=', rec.reference),
                    ('rental_status', '!=', 'done')
                ], limit=1)
                if sale_order:
                    domain.append(('group_id.name', '=', rec.reference))
                else:
                    domain.append(('id', '=', False))  # ไม่แสดงอะไร
            elif rec.partner_id:
                # ✅ กรองเฉพาะ picking ที่ sale order ยังไม่ done
                domain.append(('partner_id', '=', rec.partner_id.id))
                domain.append(('group_id.sale_id.rental_status', '!=', 'done'))
            else:
                domain.append(('id', '=', False))  # ไม่แสดงอะไร

            rec.rental_return_domain = str(domain)

    # @api.depends('partner_id', 'reference')
    # def _compute_rental_return_domain(self):
    #     """คำนวณ domain สำหรับ rental_return_select_id แบบ dynamic"""
    #     for rec in self:
    #         domain = [
    #             ('deposit_return_state', '=', 'not_returned'),
    #             ('name', 'not ilike', '%OUT%')
    #         ]
    #
    #         # กรองจาก reference ก่อนถ้ามี
    #         if rec.reference:
    #             domain.append(('group_id.name', '=', rec.reference))
    #         elif rec.partner_id:
    #             domain.append(('partner_id', '=', rec.partner_id.id))
    #         else:
    #             domain.append(('id', '=', False))  # ไม่แสดงอะไร
    #
    #         rec.rental_return_domain = str(domain)

    # # ✅ เพิ่ม compute method
    @api.depends('rental_return_select_id', 'partner_id', 'reference')
    def _compute_payment_from_reference(self):
        """
        ค้นหา Payment จาก Bill Reference

        Flow:
        1. อ่าน reference (เช่น SO-250522-0001)
        2. ค้นหา Invoice ที่ invoice_origin = reference
        3. ค้นหา Payment ที่ชำระ Invoice นั้น
        4. เก็บ Payment แรกที่พบ
        """
        for rec in self:
            # เพิ่มการตรวจสอบ: ถ้าไม่มีใบคืนการเช่าที่ถูกเลือก หรือ check_show = False ให้เคลียร์ค่าแล้วข้ามไป
            if not rec.reference or not rec.check_show:
                rec.payment_ref_id = False
                continue

            invoices = self.env['account.move'].search([
                ('invoice_origin', '=', rec.reference),  # ลองใช้ origin ของ picking เป็น reference
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('name', 'ilike', 'INS-'),
            ], limit=1)
            # print("invoices",invoices.name)
            # ถ้าไม่พบ invoices ให้เคลียร์ค่าแล้วข้ามไป
            if not invoices:
                rec.payment_ref_id = False
                # raise UserError(_("ไม่พบเอกสารค่าประกัน INS- (กรุณาตรวจสอบเอกสารให้ถูกต้อง มีการสร้างหรือ สถานะ ลงบันทึก หรือไม่)"))
                continue

            # STEP 3 & 4: ค้นหา Payment
            payment = self.env['account.payment'].search([
                # 'cash_invoice_id' น่าจะเป็นฟิลด์ที่คุณเพิ่มเอง, สมมติว่ามีค่าเป็น ID ของ Invoice
                ('search_invoice_name', '=', invoices.name),
                ('state', '=', 'posted'),
                ('payment_type', '=', 'inbound')
            ], order='date desc', limit=1)

            if payment:
                rec.payment_ref_id = payment
            else:
                rec.payment_ref_id = False
                # raise UserError(_("ไม่พบเอกสารใบรับชำระค่าประกัน (กรุณาตรวจสอบเอกสารให้ถูกต้อง มีข้อมูล อ้างอิง เลขใบแจ้งหนี้ และ สถานะ ลงบันทึก หรือไม่)"))
                continue

    @api.depends('state')  # Adjust dependencies as necessary
    def _compute_can_edit_lines(self):
        # Default logic: lines can only be edited in draft state
        for voucher in self:
            voucher.can_edit_lines = voucher.state == 'draft'

    # def _compute_reference_summary(self):
    #     for rec in self:
    #         invs = ', '.join(rec.invoice_ref_ids.mapped('name')) or '-'
    #         pays = ', '.join(rec.payment_t_ids.mapped('name')) or '-'
    #         rec.reference_summary = f"ใบแจ้งหนี้: {invs}\nใบรับชำระ: {pays}"

    @api.depends('invoice_ids', 'state', 'total_outstanding')
    def _compute_show_payment_button(self):
        for rec in self:
            # แสดงปุ่มเมื่อมีหนี้ค้างชำระและสถานะเป็น draft
            rec.show_payment_button = bool(rec.invoice_ids) and rec.state == 'draft' and rec.total_outstanding > 0

    # def action_create_payment_from_outstanding(self):
    #     """สร้างใบรับชำระจากหนี้ค้างชำระ (แก้ไขให้บันทึกประวัติแบบสะสม)"""
    #     if self.refund_of_rental == False:
    #         raise UserError(_("⚠️ อนุญาติเฉพาะการเงินส่วนกลางเท่านั้น ในการรับชำระหนี้ค้างชำระ"))
    #     else:
    #         self.ensure_one()
    #
    #         if not self.invoice_ids or self.total_outstanding <= 0:
    #             raise UserError(_("ไม่มีหนี้ค้างชำระที่เลือก หรือยอดเป็น 0"))
    #
    #         # 1) จดอ้างอิงใบแจ้งหนี้ที่เลือกไว้ก่อน (สำคัญสุด)
    #         selected_invoices = self.invoice_ids
    #         selected_invoice_ids = selected_invoices.ids
    #         snapshot_amount = self.total_outstanding
    #
    #         # 2) หา payment method "หักเงินประกันค่าเช่า"
    #         payment_method = self.env['payment.method'].search([
    #             ('name', '=', 'หักเงินประกันค่าเช่า'),
    #             ('is_active', '=', True)
    #         ], limit=1)
    #         if not payment_method:
    #             raise UserError(_("ไม่พบวิธีการชำระ 'หักเงินประกันค่าเช่า' กรุณาตั้งค่าในระบบก่อน"))
    #         if not payment_method.account_id:
    #             raise UserError(_("วิธีการชำระ 'หักเงินประกันค่าเช่า' ยังไม่ได้ตั้งค่าบัญชี"))
    #
    #         # 3) สร้าง invoice_lines และยอดรวมจาก invoice จริง
    #         invoice_lines, total_amount = [], 0.0
    #         for invoice in selected_invoices:
    #             amount_residual = invoice.amount_residual
    #             if amount_residual > 0:
    #                 invoice_lines.append((0, 0, {
    #                     'invoice_id': invoice.id,
    #                     'amount_due': amount_residual,
    #                     'amount_total': invoice.amount_total,
    #                     'paid': True,
    #                     'paid_total': amount_residual,
    #                     'wht_total': invoice.wht_amt or 0,
    #                     'wht_base': invoice.wht_base or 0,
    #                 }))
    #                 total_amount += amount_residual
    #         if not invoice_lines:
    #             raise UserError(_("ไม่มียอดค้างชำระในใบแจ้งหนี้ที่เลือก"))
    #
    #         # 4) หา journal + บัญชีปลายทาง
    #         journal = self.env['account.journal'].search([
    #             ('name', '=', 'สมุดรายวันรับชำระ')
    #         ], limit=1) or self.env['account.journal'].search([
    #             ('type', '=', 'receivable'),
    #             ('company_id', '=', self.company_id.id)
    #         ], limit=1)
    #         if not journal:
    #             raise UserError(_("ไม่พบสมุดรายวันสำหรับรับชำระเงิน"))
    #
    #         destination_account = self.partner_id.property_account_receivable_id
    #         if not destination_account:
    #             raise UserError(_("ลูกค้ายังไม่ได้ตั้งค่าบัญชีลูกหนี้"))
    #
    #         # 5) สร้าง Payment
    #         payment_vals = {
    #             'payment_type': 'inbound',
    #             'partner_type': 'customer',
    #             'partner_id': self.partner_id.id,
    #             'amount': total_amount,
    #             'currency_id': self.currency_id.id or self.company_id.currency_id.id,
    #             'date': fields.Date.today(),
    #             'journal_id': journal.id,
    #             'payment_method_one_id': payment_method.id,
    #             'is_payment_multi': False,
    #             'invoice_ids': invoice_lines,
    #             'destination_account_id': destination_account.id,
    #             'ref': f"คืนเงินประกันจาก {self.number or 'Draft Voucher'} - {self.partner_id.name}",
    #         }
    #         payment = self.env['account.payment'].create(payment_vals)
    #
    #         try:
    #             # 6) Post payment
    #             payment.action_post()
    #
    #             # 7) บันทึกอ้างอิง "สองฝั่ง" (แบบสะสม)
    #             self.invoice_ref_ids = [(4, inv_id) for inv_id in selected_invoice_ids]
    #             current_snapshot = self.outstanding_amount_snapshot
    #             self.outstanding_amount_snapshot = current_snapshot + snapshot_amount
    #
    #             # ✅ บังคับคำนวณ Line ใหม่หลังบันทึก Snapshot
    #             self._onchange_rental_return_select_id()
    #
    #             payment.voucher_source_id = self.id
    #             self.payment_t_ids = [(4, payment.id)]
    #
    #             # 8) ค่อยล้าง invoice_ids บนแบบฟอร์ม (ครั้งเดียวพอ)
    #             self.invoice_ids = [(5, 0, 0)]
    #
    #             # 9) Log
    #             self.message_post(
    #                 body=f"<p>✅ สร้างใบรับชำระสำเร็จ: <b>{payment.name}</b></p>"
    #                      f"<p>📋 ยอดเงิน: <b>{total_amount:,.2f}</b> {self.currency_id.name or 'THB'}</p>"
    #                      f"<p>💳 วิธีชำระ: <b>{payment_method.name}</b></p>"
    #             )
    #
    #             # 10) เปิดใบรับชำระที่สร้าง
    #             return {
    #                 'name': _('ใบรับชำระ'),
    #                 'type': 'ir.actions.act_window',
    #                 'res_model': 'account.payment',
    #                 'res_id': payment.id,
    #                 'view_mode': 'form',
    #                 'target': 'current',
    #             }
    #
    #         except Exception as e:
    #             if payment.exists():
    #                 payment.unlink()
    #             raise UserError(_("ไม่สามารถบันทึกใบรับชำระได้: %s") % str(e))

    @api.onchange('partner_id', 'reference')
    def _onchange_rental_return_domain(self):
        """คำนวณ domain สำหรับ rental_return_select_id"""
        domain = [
            ('deposit_return_state', '=', 'not_returned'),
            ('name', 'not ilike', '%OUT%')
        ]

        # กรองจาก reference ก่อนถ้ามี (ต้องเช็ค check_show ด้วย)
        if self.reference and self.check_show:
            # ✅ เช็ค sale.order.rental_status != 'done'
            sale_order = self.env['sale.order'].search([
                ('name', '=', self.reference),
                ('rental_status', '!=', 'done')
            ], limit=1)
            if sale_order:
                domain.append(('group_id.name', '=', self.reference))
            else:
                # ✅ แก้ไข: เพิ่ม or '' ป้องกัน error
                raise UserError(
                    _("ลูกค้า %s ได้ปิดบิล %s เรียบร้อยแล้ว") % (self.partner_id.name or '', self.reference))
        elif self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
            domain.append(('group_id.sale_id.rental_status', '!=', 'done'))
        else:
            domain.append(('id', '=', False))

        return {
            'domain': {
                'rental_return_select_id': domain
            }
        }

    # @api.onchange('partner_id', 'reference')
    # def _onchange_rental_return_domain(self):
    #     """คำนวณ domain สำหรับ rental_return_select_id"""
    #     domain = [
    #         ('deposit_return_state', '=', 'not_returned'),
    #         ('name', 'not ilike', '%OUT%')
    #     ]
    #
    #     # กรองจาก reference ก่อนถ้ามี
    #     if self.reference:
    #         domain.append(('group_id.name', '=', self.reference))
    #     elif self.partner_id:
    #         domain.append(('partner_id', '=', self.partner_id.id))
    #     else:
    #         domain.append(('id', '=', False))
    #
    #     return {
    #         'domain': {
    #             'rental_return_select_id': domain
    #         }
    #     }

    @api.onchange('partner_id', 'voucher_type', 'reference')
    def _onchange_partner_filter_invoices(self):
        """กรอง Invoice ที่แสดงใน Dropdown แบบเข้มงวด + อัปเดต Picking"""

        # 1. อัปเดต rental_return_select_id ตาม reference หรือ partner (ต้องเช็ค check_show ด้วย)
        if self.reference and self.check_show:
            # ✅ เช็ค sale.order.rental_status != 'done' ก่อน
            sale_order = self.env['sale.order'].search([
                ('name', '=', self.reference),
                ('rental_status', '!=', 'done')
            ], limit=1)

            if not sale_order:
                # ✅ แจ้งเตือนว่าปิดบิลแล้ว
                self.rental_return_select_id = False
                self.rental_return_id = False
                raise UserError(
                    _("ลูกค้า %s ได้ปิดบิล %s เรียบร้อยแล้ว") % (self.partner_id.name or '', self.reference))

            # ✅ กรองจาก reference ก่อน (เลือกเลขรันที่ใหญ่ที่สุด)
            picks = self.env['stock.picking'].search([
                ('group_id.name', '=', self.reference),
                ('deposit_return_state', '=', 'not_returned'),
                ('name', 'not ilike', '%OUT%')
            ], order='name desc', limit=1)

            self.rental_return_select_id = picks.id or False

            if self.rental_return_select_id:
                self.rental_return_id = self.rental_return_select_id

        elif self.partner_id:
            # ✅ กรองเฉพาะ picking ที่ sale order ยังไม่ done
            picks = self.env['stock.picking'].search([
                ('partner_id', '=', self.partner_id.id),
                ('deposit_return_state', '=', 'not_returned'),
                ('name', 'not ilike', '%OUT%'),
                ('group_id.sale_id.rental_status', '!=', 'done')
            ], order='name desc', limit=1)

            self.rental_return_select_id = picks.id or False

            if self.rental_return_select_id:
                self.rental_return_id = self.rental_return_select_id

        # 2. คำนวณ domain สำหรับ invoice_ids
        domain = self._get_invoice_domain()

        # 3. ค้นหา Invoice ที่ตรงเงื่อนไข (สำหรับ Debug)
        if self.partner_id:
            invoices = self.env['account.move'].search(domain)

            # 🔍 Debug
            print(f"\n[FILTER] Partner: {self.partner_id.name}")
            if self.reference:
                print(f"[FILTER] Reference: {self.reference}")
            print(f"[FILTER] Valid {len(invoices)} invoices:")
            for inv in invoices:
                print(f"  - {inv.name}: Residual={inv.amount_residual}, State={inv.payment_state}")

        return {
            'domain': {
                'invoice_ids': domain
            }
        }

    # @api.onchange('partner_id', 'voucher_type', 'reference')
    # def _onchange_partner_filter_invoices(self):
    #     """กรอง Invoice ที่แสดงใน Dropdown แบบเข้มงวด + อัปเดต Picking"""
    #
    #     # เรียกใช้ onchange สำหรับ rental_return_select_id
    #     result = self._onchange_rental_return_domain()
    #
    #     # 1. อัปเดต rental_return_select_id ตาม reference หรือ partner
    #     if self.reference:
    #         picks = self.env['stock.picking'].search([
    #             ('group_id.name', '=', self.reference),
    #             ('deposit_return_state', '=', 'not_returned'),
    #             ('name', 'not ilike', '%OUT%')
    #         ], order='name desc', limit=1)
    #
    #         self.rental_return_select_id = picks.id or False
    #
    #         if self.rental_return_select_id:
    #             self.rental_return_id = self.rental_return_select_id
    #
    #     elif self.partner_id:
    #         picks = self.env['stock.picking'].search([
    #             ('partner_id', '=', self.partner_id.id),
    #             ('deposit_return_state', '=', 'not_returned'),
    #             ('name', 'not ilike', '%OUT%')
    #         ], order='name desc', limit=1)
    #
    #         self.rental_return_select_id = picks.id or False
    #
    #         if self.rental_return_select_id:
    #             self.rental_return_id = self.rental_return_select_id
    #
    #     # 2. คำนวณ domain สำหรับ invoice_ids
    #     domain = self._get_invoice_domain()
    #
    #     # 3. รวม domain ทั้งสอง
    #     if result:
    #         result['domain']['invoice_ids'] = domain
    #     else:
    #         result = {'domain': {'invoice_ids': domain}}
    #
    #     return result

    # def action_create_payment_from_outstanding(self):
    #     """สร้างใบรับชำระแยกใบตามจำนวน Invoice ที่เลือก"""
    #     if self.refund_of_rental == False:
    #         raise UserError(_("⚠️ อนุญาติเฉพาะการเงินส่วนกลางเท่านั้น ในการรับชำระหนี้ค้างชำระ"))
    #
    #     self.ensure_one()
    #
    #     if not self.invoice_ids or self.total_outstanding <= 0:
    #         raise UserError(_("ไม่มีหนี้ค้างชำระที่เลือก หรือยอดเป็น 0"))
    #
    #     # 1) จดอ้างอิงใบแจ้งหนี้ที่เลือกไว้ก่อน
    #     selected_invoices = self.invoice_ids
    #     selected_invoice_ids = selected_invoices.ids
    #     snapshot_amount = self.total_outstanding
    #
    #     # 2) หา payment method "หักเงินประกันค่าเช่า"
    #     payment_method = self.env['payment.method'].search([
    #         ('name', '=', 'หักเงินประกันค่าเช่า'),
    #         ('is_active', '=', True)
    #     ], limit=1)
    #     if not payment_method:
    #         raise UserError(_("ไม่พบวิธีการชำระ 'หักเงินประกันค่าเช่า' กรุณาตั้งค่าในระบบก่อน"))
    #     if not payment_method.account_id:
    #         raise UserError(_("วิธีการชำระ 'หักเงินประกันค่าเช่า' ยังไม่ได้ตั้งค่าบัญชี"))
    #
    #     # 3) หา journal + บัญชีปลายทาง
    #     journal = self.env['account.journal'].search([
    #         ('name', '=', 'สมุดรายวันรับชำระ')
    #     ], limit=1) or self.env['account.journal'].search([
    #         ('type', '=', 'receivable'),
    #         ('company_id', '=', self.company_id.id)
    #     ], limit=1)
    #     if not journal:
    #         raise UserError(_("ไม่พบสมุดรายวันสำหรับรับชำระเงิน"))
    #
    #     destination_account = self.partner_id.property_account_receivable_id
    #     if not destination_account:
    #         raise UserError(_("ลูกค้ายังไม่ได้ตั้งค่าบัญชีลูกหนี้"))
    #
    #     # 4) สร้าง Payment แยกใบ ตามจำนวน Invoice
    #     created_payments = self.env['account.payment']
    #
    #     for invoice in selected_invoices:
    #         amount_residual = invoice.amount_residual
    #         if amount_residual <= 0:
    #             continue
    #
    #         # สร้าง invoice_lines สำหรับ Invoice นี้เท่านั้น
    #         invoice_lines = [(0, 0, {
    #             'invoice_id': invoice.id,
    #             'amount_due': amount_residual,
    #             'amount_total': invoice.amount_total,
    #             'paid': True,
    #             'paid_total': amount_residual,
    #             'wht_total': invoice.wht_amt or 0,
    #             'wht_base': invoice.wht_base or 0,
    #         })]
    #
    #         # สร้าง Payment สำหรับ Invoice นี้
    #         payment_vals = {
    #             'payment_type': 'inbound',
    #             'partner_type': 'customer',
    #             'partner_id': self.partner_id.id,
    #             'amount': amount_residual,
    #             'currency_id': self.currency_id.id or self.company_id.currency_id.id,
    #             'date': fields.Date.today(),
    #             'journal_id': journal.id,
    #             'payment_method_one_id': payment_method.id,
    #             'is_payment_multi': False,
    #             'invoice_ids': invoice_lines,
    #             'destination_account_id': destination_account.id,
    #             'ref': f"คืนเงินประกันจาก {self.number or 'Draft Voucher'} - {invoice.name}",
    #         }
    #
    #         payment = self.env['account.payment'].create(payment_vals)
    #
    #         try:
    #             # Post payment
    #             payment.action_post()
    #             payment.voucher_source_id = self.id
    #             created_payments |= payment
    #
    #             # Log
    #             print(f"✅ สร้าง Payment: {payment.name} สำหรับ Invoice: {invoice.name} ({amount_residual:,.2f})")
    #
    #         except Exception as e:
    #             if payment.exists():
    #                 payment.unlink()
    #             raise UserError(_("ไม่สามารถบันทึกใบรับชำระสำหรับ %s: %s") % (invoice.name, str(e)))
    #
    #     # 5) บันทึกอ้างอิง "สองฝั่ง" (แบบสะสม)
    #     if created_payments:
    #         self.invoice_ref_ids = [(4, inv_id) for inv_id in selected_invoice_ids]
    #         current_snapshot = self.outstanding_amount_snapshot
    #         self.outstanding_amount_snapshot = current_snapshot + snapshot_amount
    #
    #         # ✅ บังคับคำนวณ Line ใหม่หลังบันทึก Snapshot
    #         self._onchange_rental_return_select_id()
    #
    #         # บันทึก Payment ทั้งหมด
    #         for payment in created_payments:
    #             self.payment_t_ids = [(4, payment.id)]
    #
    #         # ล้าง invoice_ids บนแบบฟอร์ม
    #         self.invoice_ids = [(5, 0, 0)]
    #
    #         # Log สรุป
    #         payment_names = ', '.join(created_payments.mapped('name'))
    #         self.message_post(
    #             body=f"<p>✅ สร้างใบรับชำระสำเร็จ {len(created_payments)} ใบ:</p>"
    #                  f"<p><b>{payment_names}</b></p>"
    #                  f"<p>📋 ยอดเงินรวม: <b>{snapshot_amount:,.2f}</b> {self.currency_id.name or 'THB'}</p>"
    #                  f"<p>💳 วิธีชำระ: <b>{payment_method.name}</b></p>"
    #         )
    #
    #         # 6) เปิด Tree View แสดง Payment ที่สร้าง
    #         return {
    #             'name': _('ใบรับชำระ'),
    #             'type': 'ir.actions.act_window',
    #             'res_model': 'account.payment',
    #             'view_mode': 'tree,form',
    #             'domain': [('id', 'in', created_payments.ids)],
    #             'target': 'current',
    #         }
    #     else:
    #         raise UserError(_("ไม่สามารถสร้างใบรับชำระได้"))
    def action_create_payment_from_outstanding(self):
        """สร้างใบรับชำระแยกใบตามจำนวน Invoice ที่เลือก"""
        if self.refund_of_rental == False:
            raise UserError(_("⚠️ อนุญาตเฉพาะการเงินส่วนกลางเท่านั้น ในการรับชำระหนี้ค้างชำระ"))

        self.ensure_one()

        if not self.invoice_ids or self.total_outstanding <= 0:
            raise UserError(_("ไม่มีหนี้ค้างชำระที่เลือก หรือยอดเป็น 0"))

        # 1) จดจำอ้างอิงใบแจ้งหนี้ที่เลือกไว้ก่อน
        selected_invoices = self.invoice_ids
        selected_invoice_ids = selected_invoices.ids
        snapshot_amount = self.total_outstanding

        # 2) หา payment method "หักเงินประกันค่าเช่า"
        payment_method = self.env['payment.method'].search([
            ('name', '=', 'หักเงินประกันค่าเช่า'),
            ('is_active', '=', True)
        ], limit=1)
        if not payment_method:
            raise UserError(_("ไม่พบวิธีการชำระ 'หักเงินประกันค่าเช่า' กรุณาตั้งค่าในระบบก่อน"))
        if not payment_method.account_id:
            raise UserError(_("วิธีการชำระ 'หักเงินประกันค่าเช่า' ยังไม่ได้ตั้งค่าบัญชี"))

        # 3) ✅ ฟังก์ชันเลือก Journal ตามประเภทใบแจ้งหนี้
        def get_journal_for_invoice(invoice):
            """
            เลือก journal ตามเลขที่ใบแจ้งหนี้:
            - INV-* → สมุดรายวันรับชำระ
            - ILS-* → สมุดรายวันรับชำระค่าปรับหาย
            - IBK-* → สมุดรายวันรับชำระค่าปรับชำรุด
            """
            invoice_name = invoice.name or ""

            # กำหนด mapping ระหว่าง prefix กับชื่อ journal
            journal_mapping = {
                'INV': 'สมุดรายวันรับชำระ',
                'ILS': 'สมุดรายวันรับชำระค่าปรับหาย',
                'IBK': 'สมุดรายวันรับชำระค่าปรับชำรุด',
            }

            # ค้นหา journal ที่ตรงกับ invoice prefix
            for prefix, journal_name in journal_mapping.items():
                if invoice_name.startswith(prefix):
                    journal = self.env['account.journal'].search([
                        ('name', '=', journal_name),
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)

                    if journal:
                        print(f"✅ เลือก Journal: {journal.name} สำหรับ Invoice: {invoice_name}")
                        return journal
                    else:
                        raise UserError(
                            _("ไม่พบ '%s' สำหรับใบแจ้งหนี้ %s\nกรุณาสร้าง Journal ในระบบ")
                            % (journal_name, invoice_name)
                        )

            # ถ้าไม่ตรงกับ prefix ใดๆ → ใช้ default journal
            default_journal = self.env['account.journal'].search([
                ('name', '=', 'สมุดรายวันรับชำระ'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)

            if not default_journal:
                default_journal = self.env['account.journal'].search([
                    ('type', '=', 'receivable'),
                    ('company_id', '=', self.company_id.id)
                ], limit=1)

            if not default_journal:
                raise UserError(_("ไม่พบสมุดรายวันสำหรับรับชำระเงิน"))

            print(f"⚠️ ใช้ Default Journal: {default_journal.name} สำหรับ Invoice: {invoice_name}")
            return default_journal

        # 4) หาบัญชีปลายทาง
        destination_account = self.partner_id.property_account_receivable_id
        if not destination_account:
            raise UserError(_("ลูกค้ายังไม่ได้ตั้งค่าบัญชีลูกหนี้"))

        # 5) สร้าง Payment แยกใบ ตามจำนวน Invoice
        created_payments = self.env['account.payment']

        for invoice in selected_invoices:
            amount_residual = invoice.amount_residual
            if amount_residual <= 0:
                continue

            # ✅ เลือก Journal ที่เหมาะสมตามประเภทใบแจ้งหนี้
            journal = get_journal_for_invoice(invoice)

            # สร้าง invoice_lines สำหรับ Invoice นี้เท่านั้น
            invoice_lines = [(0, 0, {
                'invoice_id': invoice.id,
                'amount_due': amount_residual,
                'amount_total': invoice.amount_total,
                'paid': True,
                'paid_total': amount_residual,
                'wht_total': invoice.wht_amt or 0,
                'wht_base': invoice.wht_base or 0,
            })]

            # สร้าง Payment สำหรับ Invoice นี้
            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': self.partner_id.id,
                'amount': amount_residual,
                'currency_id': self.currency_id.id or self.company_id.currency_id.id,
                # 'date': fields.Date.today(),
                'date': self.date,
                'journal_id': journal.id,  # ✅ ใช้ journal ที่เลือกตามประเภทใบแจ้งหนี้
                'payment_method_one_id': payment_method.id,
                'is_payment_multi': False,
                'invoice_ids': invoice_lines,
                'destination_account_id': destination_account.id,
                'search_invoice_name': invoice.name,
                'ref': f"เปิดบิลเช่าหักจากเงินประกัน {self.number or 'Draft Voucher'} - {invoice.name}",
            }

            payment = self.env['account.payment'].create(payment_vals)

            try:
                # Post payment
                payment.action_post()
                payment.voucher_source_id = self.id
                created_payments |= payment

                # Log
                print(
                    f"✅ สร้าง Payment: {payment.name} | Journal: {journal.name} | Invoice: {invoice.name} ({amount_residual:,.2f})")

            except Exception as e:
                if payment.exists():
                    payment.unlink()
                raise UserError(_("ไม่สามารถบันทึกใบรับชำระสำหรับ %s: %s") % (invoice.name, str(e)))

        # 6) บันทึกอ้างอิง "สองขั้ง" (แบบสะสม)
        if created_payments:
            self.invoice_ref_ids = [(4, inv_id) for inv_id in selected_invoice_ids]
            current_snapshot = self.outstanding_amount_snapshot
            self.outstanding_amount_snapshot = current_snapshot + snapshot_amount

            # ✅ บังคับคำนวณ Line ใหม่หลังบันทึก Snapshot
            self._onchange_rental_return_select_id()

            # บันทึก Payment ทั้งหมด
            for payment in created_payments:
                self.payment_t_ids = [(4, payment.id)]

            # ล้าง invoice_ids บนแบบฟอร์ม
            self.invoice_ids = [(5, 0, 0)]

            # Log สรุป
            payment_names = ', '.join(created_payments.mapped('name'))
            self.message_post(
                body=f"<p>✅ สร้างใบรับชำระสำเร็จ {len(created_payments)} ใบ:</p>"
                     f"<p><b>{payment_names}</b></p>"
                     f"<p>📋 ยอดเงินรวม: <b>{snapshot_amount:,.2f}</b> {self.currency_id.name or 'THB'}</p>"
                     f"<p>💳 วิธีชำระ: <b>{payment_method.name}</b></p>"
            )

            # 7) เปิด Tree View แสดง Payment ที่สร้าง
            return {
                'name': _('ใบรับชำระ'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', created_payments.ids)],
                'target': 'current',
            }
        else:
            raise UserError(_("ไม่สามารถสร้างใบรับชำระได้"))

    @api.depends('partner_id', 'voucher_type', 'state')
    def _compute_available_invoice_ids(self):
        """คำนวณรายการ Invoice ที่สามารถเลือกได้"""
        for rec in self:
            if not rec.partner_id:
                rec.available_invoice_ids = [(5, 0, 0)]  # Clear all
                continue

            # ค้นหา Invoice ที่ตรงเงื่อนไข
            domain = [
                ('partner_id', '=', rec.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                # ('payment_state', 'in', ['not_paid', 'partial']),
                ('amount_residual', '>', 0),

            ]

            invoices = self.env['account.move'].search(domain)
            rec.available_invoice_ids = [(6, 0, invoices.ids)]

            # Debug
            print(f"\n[COMPUTE] Partner: {rec.partner_id.name}")
            print(f"[COMPUTE] Available {len(invoices)} invoices:")
            for inv in invoices:
                print(f"  - {inv.name}: Residual={inv.amount_residual}")

    @api.depends('invoice_ids', 'state', 'total_outstanding')
    def _compute_show_payment_button(self):
        for rec in self:
            # แสดงปุ่มเมื่อมีหนี้ค้างชำระและสถานะเป็น draft
            rec.show_payment_button = bool(rec.invoice_ids) and rec.state == 'draft' and rec.total_outstanding > 0

    # payment_t_ids = fields.Many2many('account.payment', string="Payments")

    # ==== SECTION: depends/onchange blocks (fixed) =================================

    @api.depends('invoice_ids')
    def _compute_total_outstanding(self):
        """คำนวณยอดหนี้ค้างชำระรวม (ยอดคงเหลือของใบแจ้งหนี้ที่เลือก)"""
        for rec in self:
            # ✅ ถ้า check_show = False ให้ข้ามไปเลย
            if not rec.check_show:
                rec.total_outstanding = 0.0
                continue

            if not rec.invoice_ids:
                rec.total_outstanding = 0.0
                print(f"[COMPUTE] Voucher: {rec.number or 'Draft'}, No invoices selected, Total: 0.00")
                continue

            # ✅ บังคับ Refresh ข้อมูล Invoice
            fresh_invoices = self.env['account.move'].browse(rec.invoice_ids.ids)
            fresh_invoices.invalidate_cache(['amount_residual', 'payment_state'])

            # ดึงข้อมูล amount_residual จาก invoices ที่เลือก
            total = sum(fresh_invoices.mapped('amount_residual'))
            rec.total_outstanding = total

            # 🔍 Debug: แสดงรายละเอียด
            print(f"\n[COMPUTE] Voucher: {rec.number or 'Draft'}, Total Outstanding: {total}")
            for inv in fresh_invoices:
                print(f"  - Invoice: {inv.name}, Residual: {inv.amount_residual}, State: {inv.payment_state}")

    @api.onchange('reference')
    def _onchange_reference(self):
        """อัปเดต rental_return_select_id เมื่อ reference เปลี่ยน"""
        # ✅ เพิ่มเงื่อนไข check_show
        if self.reference and self.check_show:
            # ✅ เช็ค sale.order.rental_status != 'done' ก่อน
            sale_order = self.env['sale.order'].search([
                ('name', '=', self.reference),
                ('rental_status', '!=', 'done')
            ], limit=1)

            if not sale_order:
                # ✅ แจ้งเตือนว่าปิดบิลแล้ว
                self.rental_return_select_id = False
                self.rental_return_id = False
                raise UserError(
                    _("ลูกค้า %s ได้ปิดบิล %s เรียบร้อยแล้ว") % (self.partner_id.name or '', self.reference))

            # ค้นหา picking ที่ตรงกับ reference (เลขรันใหญ่สุด)
            picks = self.env['stock.picking'].search([
                ('group_id.name', '=', self.reference),
                ('deposit_return_state', '=', 'not_returned'),
                ('name', 'not ilike', '%OUT%')
            ], order='name desc', limit=1)

            if picks:
                self.rental_return_select_id = picks.id
                self.rental_return_id = picks.id

                # Debug
                print(f"\n[REFERENCE CHANGE] Found Picking: {picks.name}")
                print(f"[REFERENCE CHANGE] Reference: {self.reference}")

    # @api.onchange('reference')
    # def _onchange_reference(self):
    #     """อัปเดต rental_return_select_id เมื่อ reference เปลี่ยน"""
    #     if self.reference:
    #         # ค้นหา picking ที่ตรงกับ reference (เลขรันใหญ่สุด)
    #         picks = self.env['stock.picking'].search([
    #             ('group_id.name', '=', self.reference),
    #             ('deposit_return_state', '=', 'not_returned'),
    #             ('name', 'not ilike', '%OUT%')
    #         ], order='name desc', limit=1)
    #
    #         if picks:
    #             self.rental_return_select_id = picks.id
    #             self.rental_return_id = picks.id
    #
    #             # Debug
    #             print(f"\n[REFERENCE CHANGE] Found Picking: {picks.name}")
    #             print(f"[REFERENCE CHANGE] Reference: {self.reference}")

    @api.model
    def _get_invoice_domain(self):
        """คำนวณ domain สำหรับ invoice_ids แบบ dynamic (ใช้ทุกครั้งที่เปิด dropdown)"""

        # ถ้าไม่มี partner → ไม่แสดงอะไร
        if not self.partner_id:
            return [('id', '=', False)]

        # ค้นหา Invoice ที่ตรงเงื่อนไข
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            # ('payment_state', 'in', ['not_paid', 'partial']),
            ('amount_residual', '>', 0),
            # ('name', 'ilike', 'INV-'),
        ]

        return domain

    @api.onchange('invoice_ids')
    def _onchange_invoice_ids_proxy(self):
        """บังคับคำนวณยอดหนี้ค้างชำระรวม และเรียก logic ที่เกี่ยวข้องกับการคืนค่าเช่า"""

        # ✅ บังคับ Refresh ข้อมูล Invoice ก่อนใช้งาน
        if self.invoice_ids:
            # อ่านข้อมูลใหม่จากฐานข้อมูล (ไม่ใช้ Cache)
            fresh_invoices = self.env['account.move'].browse(self.invoice_ids.ids)
            fresh_invoices.invalidate_cache(['amount_residual', 'payment_state'])

            # บังคับให้อ่านค่าใหม่
            for inv in fresh_invoices:
                _ = inv.amount_residual  # บังคับ Compute
                _ = inv.payment_state  # บังคับ Compute

        # 1) บังคับคำนวณ total_outstanding ก่อน
        self._compute_total_outstanding()

        # 2) Debug: แสดงยอดรวมแบบละเอียด
        if self.invoice_ids:
            total = sum(self.invoice_ids.mapped('amount_residual'))
            print(f"\n[ONCHANGE] Selected Invoices: {len(self.invoice_ids)}, Total Outstanding: {total}")
            for inv in self.invoice_ids:
                print(f"  - {inv.name}: Residual={inv.amount_residual}, State={inv.payment_state}")
        else:
            print("[ONCHANGE] No invoices selected, Total Outstanding: 0.00")

        # 3) เรียก logic เดิมเพื่อให้บรรทัด/Unit Price อัปเดตทันที (ถ้ามี)
        self._onchange_rental_return_select_id()

    @api.onchange('rental_return_select_id', 'rental_return_id', 'no_deduction', 'invoice_ids')
    def _onchange_rental_return_select_id(self):

        def _to_float(v):
            try:
                return float(v or 0.0)
            except Exception:
                return 0.0

        for record in self:
            record.check_type_show = 'show' if record.partner_id else ''

            def _remove_line(prod=None, name=None):
                if record.id:
                    dom = [('voucher_id', '=', record.id)]
                    if prod:
                        dom.append(('product_id', '=', prod.id))
                    else:
                        dom += [('product_id', '=', False), ('name', '=', name)]
                    record.env['account.voucher.line'].search(dom).unlink()
                else:
                    olds = (record.line_ids.filtered(lambda l: l.product_id == prod) if prod
                            else record.line_ids.filtered(lambda l: not l.product_id and l.name == name))
                    if olds:
                        record.line_ids -= olds

            # ไม่มีใบคืน → ล้างรายการที่เกี่ยวข้อง
            if not record.rental_return_select_id:
                prod_dep = record.env['product.product'].search([('name', '=', "เงินประกันค่าเช่า")], limit=1)
                if prod_dep:
                    _remove_line(prod=prod_dep)
                # ปิดการใช้งาน ค่าเช่าเครื่องมือก่อสร้าง - เก็บไว้อ้างอิง
                # _remove_line(prod=None, name="ค่าเช่าเครื่องมือก่อสร้าง")
                continue

            picking = record.env['stock.picking'].browse(record.rental_return_select_id.id)
            if not picking:
                continue

            record.rental_return_id = record.rental_return_select_id
            # ✅ เพิ่มเงื่อนไข check_show ก่อน set reference
            if record.check_show:
                record.reference = picking.group_id.name

            # หา picking ต้นทาง
            if picking.origin:

                related_picking = record.env['stock.picking'].browse(record.rental_return_select_id.id)
                # print("related_picking",related_picking)
            else:
                related_picking = False

            if not related_picking:
                prod_dep = record.env['product.product'].search([('name', '=', "เงินประกันค่าเช่า")], limit=1)
                if prod_dep:
                    _remove_line(prod=prod_dep)
                # ปิดการใช้งาน ค่าเช่าเครื่องมือก่อสร้าง - เก็บไว้อ้างอิง
                # _remove_line(prod=None, name="ค่าเช่าเครื่องมือก่อสร้าง")
                continue

            # ---- ค่าพื้นฐาน ----
            pfb_amount = _to_float(related_picking.sale_id.pfb_amount if related_picking.sale_id else 0.0)
            amount_untaxed = _to_float(related_picking.sale_id.amount_untaxed if related_picking.sale_id else 0.0)
            if related_picking.approval_state == 'approved':

                total_rental_discount = related_picking.rent_discount
            else:
                total_rental_discount = 0.0
            # print('name', related_picking.name)
            sx = picking.start_x_date.date() if isinstance(picking.start_x_date, datetime) else picking.start_x_date
            ex = picking.end_x_date.date() if isinstance(picking.end_x_date, datetime) else picking.end_x_date
            fx = picking.return_date.date() if isinstance(picking.return_date, datetime) else picking.return_date

            if sx and ex and fx:
                total_days = (ex - sx).days or 1
                actual_days = (fx - sx).days or 1
                amount_total_so = _to_float(related_picking.sale_id.amount_total if related_picking.sale_id else 0.0)
                daily_cost = round((amount_total_so + total_rental_discount) / total_days, 2) if total_days > 0 else 0.0
                value_16 = daily_cost * (actual_days - total_days)
            else:
                value_16 = 0.0

            # # ส่วนต่างค่าเช่า (value_18)
            # if not related_picking.sale_id.deposit_ref:
            #     if getattr(related_picking.sale_id.pricelist_id, 'name', '') == 'เรทเดือน':
            #         dd = (1 if (fx == sx) else (fx - sx).days)
            #         value_18 = (0 - total_rental_discount) if dd < 30 else (value_16 - total_rental_discount)
            #     else:
            #         value_18 = value_16 - total_rental_discount
            # else:
            #     value_18 = value_16 - total_rental_discount

            # =====================================================
            # ส่วนต่างค่าเช่า (value_18) - แก้ไขใหม่
            # =====================================================
            deposit_ref = related_picking.sale_id.deposit_ref or ''
            deposit_count = len(deposit_ref.split(',')) if deposit_ref else 0

            # Debug: แสดงค่าเริ่มต้น
            print("\n" + "=" * 60)
            print("🔍 DEBUG: คำนวณ value_18")
            print("=" * 60)
            print(f"deposit_ref: {deposit_ref}")
            print(f"deposit_count: {deposit_count}")
            print(f"value_16 (ค่าเช่าส่วนต่าง): {value_16}")
            print(f"total_rental_discount: {total_rental_discount}")
            print(f"pricelist: {getattr(related_picking.sale_id.pricelist_id, 'name', '')}")
            print(f"start_x_date (sx): {sx}")
            print(f"end_x_date (ex): {ex}")
            print(f"return_date (fx): {fx}")

            # ถ้าไม่มี deposit_ref (บิลที่ไม่ต่ออายุ)
            if deposit_count == 0:
                print("\n📌 CASE: ไม่มี deposit_ref (บิลไม่ต่ออายุ)")

                # ✅ เช็คว่า SO นี้ถูกอ้างอิงใน deposit_ref ของ SO อื่นหรือไม่
                is_referenced_by_other = record.env['sale.order'].search([
                    ('deposit_ref', '=', related_picking.sale_id.name),
                    ('state', '=', 'sale')
                ], limit=1)

                print(f"  - SO: {related_picking.sale_id.name}")
                print(
                    f"  - is_referenced_by_other: {is_referenced_by_other.name if is_referenced_by_other else 'ไม่มี'}")

                # ✅ เช็คโปรโมชั่นส่งฟรีก่อน
                campaign_name = getattr(related_picking.sale_id.campaign_id, 'name', '') or ''

                if campaign_name in ['โปร 2026 ส่งฟรีไม่เกิน 25 Km.', 'โปร 2026 ส่งฟรีไม่เกิน 35 Km.']:
                    print(f"  - campaign = {campaign_name} (โปรส่งฟรี)")
                    today_date = fields.Date.today()
                    if today_date > ex:
                        value_18 = (value_16 - total_rental_discount)
                        print(
                            f"  - วันปัจจุบัน > end_x_date → value_18 = {value_16} - {total_rental_discount} = {value_18}")
                    else:
                        value_18 = (0 - total_rental_discount)
                        print(f"  - วันปัจจุบัน <= end_x_date → value_18 = 0 - {total_rental_discount} = {value_18}")

                elif 'เรทเดือน' in getattr(related_picking.sale_id.pricelist_id, 'name', ''):
                    dd = (1 if (fx == sx) else (fx - sx).days)
                    print(f"  - pricelist contains เรทเดือน")
                    print(f"  - dd (จำนวนวัน): {dd}")

                    # ✅ เช็ค deposit_count == 0 และไม่ถูก SO อื่นอ้างอิง
                    if deposit_count == 0 and not is_referenced_by_other and fx <= ex:
                        value_18 = (0 - total_rental_discount)
                        print(
                            f"  - deposit_count == 0 และไม่ถูกอ้างอิง → value_18 = 0 - {total_rental_discount} = {value_18}")

                    elif deposit_count == 0 and not is_referenced_by_other and fx > ex:
                        value_18 = (value_16 - total_rental_discount)
                        print(
                            f"  - deposit_count == 0 แต่ถูกอ้างอิงโดย {is_referenced_by_other.name} → value_18 = {value_16} - {total_rental_discount} = {value_18}")

                    elif deposit_count == 0 and is_referenced_by_other and fx > ex:
                        value_18 = (value_16 - total_rental_discount)
                        print(
                            f"  - deposit_count == 0 แต่ถูกอ้างอิงโดย {is_referenced_by_other.name} → value_18 = {value_16} - {total_rental_discount} = {value_18}")

                    # ✅ deposit_count == 0 แต่ถูก SO อื่นอ้างอิง (SO ต้นทางที่ถูกต่ออายุ)
                    elif deposit_count == 0 and is_referenced_by_other:
                        # value_18 = (value_16 - total_rental_discount)
                        # print(
                        #     f"  - deposit_count == 0 แต่ถูกอ้างอิงโดย {is_referenced_by_other.name} → value_18 = {value_16} - {total_rental_discount} = {value_18}")
                        value_18 = (0 - total_rental_discount)
                        print(
                            f"  - deposit_count == 0 และไม่ถูกอ้างอิง → value_18 = 0 - {total_rental_discount} = {value_18}")

                    else:
                        if dd < 30:
                            value_18 = (0 - total_rental_discount)
                            print(f"  - dd < 30 → value_18 = 0 - {total_rental_discount} = {value_18}")
                        else:
                            value_18 = (value_16 - total_rental_discount)
                            print(f"  - dd >= 30 → value_18 = {value_16} - {total_rental_discount} = {value_18}")
                else:
                    value_18 = value_16 - total_rental_discount
                    print(f"  - pricelist ≠ เรทเดือน")
                    print(f"  - value_18 = {value_16} - {total_rental_discount} = {value_18}")

            else:
                # มี deposit_ref (บิลต่ออายุ)
                print("\n📌 CASE: มี deposit_ref (บิลต่ออายุ)")

                # ✅ ดึงทุก ref จาก deposit_ref (ไม่ใช่แค่ตัวสุดท้าย)
                deposit_refs = [ref.strip() for ref in deposit_ref.split(',')]
                print(f"  - deposit_refs (list): {deposit_refs}")

                # ✅ ค้นหา stock.picking ทั้งหมดจากทุก ref
                related_pickings = record.env['stock.picking'].search([
                    ('group_id.name', 'in', deposit_refs)
                ])

                print(f"  - found pickings: {len(related_pickings)} รายการ")
                for rp in related_pickings:
                    rp_end_date = rp.end_x_date.date() if isinstance(rp.end_x_date, datetime) else rp.end_x_date
                    print(f"    - {rp.name} | group: {rp.group_id.name} | end_x_date: {rp_end_date}")

                # ✅ เช็คว่ามี end_x_date ที่ != ex หรือไม่
                # มี = 1 (มีความแตกต่าง), ไม่มี = 0 (ทุกตัวเท่ากัน)
                has_diff_end_date = 0
                if related_pickings:
                    for rp in related_pickings:
                        rp_end_date = rp.end_x_date.date() if isinstance(rp.end_x_date, datetime) else rp.end_x_date
                        if rp_end_date != ex:
                            has_diff_end_date = 1
                            break

                print(f"  - current end_x_date (ex): {ex}")
                print(
                    f"  - has_diff_end_date: {has_diff_end_date} {'(มีความแตกต่าง)' if has_diff_end_date == 1 else '(ทุกตัวเท่ากัน)'}")

                if related_pickings:
                    # ✅ ใช้ has_diff_end_date == 0 แทน prev_end_x_date == ex
                    if has_diff_end_date == 0 and fx <= ex:
                        print("\n  📍 SUB-CASE: ทุก end_x_date เท่ากัน และ วันที่คืน <= วันสิ้นสุด")

                        # ✅ เช็คโปรโมชั่นส่งฟรีก่อน
                        campaign_name = getattr(related_picking.sale_id.campaign_id, 'name', '') or ''

                        if campaign_name in ['โปร 2026 ส่งฟรีไม่เกิน 25 Km.', 'โปร 2026 ส่งฟรีไม่เกิน 35 Km.']:
                            print(f"    - campaign = {campaign_name} (โปรส่งฟรี)")
                            value_18 = (0 - total_rental_discount)
                            print(f"    - โปรส่งฟรี → value_18 = 0 - {total_rental_discount} = {value_18}")

                        # วันสิ้นสุดเหมือนกัน → ใช้ logic เรทเดือน
                        elif 'เรทเดือน' in getattr(related_picking.sale_id.pricelist_id, 'name', ''):
                            dd = (1 if (fx == sx) else (fx - sx).days)
                            print(f"    - pricelist contains เรทเดือน")
                            print(f"    - dd (จำนวนวัน): {dd}")

                            if dd < 30:
                                value_18 = (0 - total_rental_discount)
                                print(f"    - dd < 30 → value_18 = 0 - {total_rental_discount} = {value_18}")
                            else:
                                value_18 = (value_16 - total_rental_discount)
                                print(f"    - dd >= 30 → value_18 = {value_16} - {total_rental_discount} = {value_18}")
                        else:
                            value_18 = value_16 - total_rental_discount
                            print(f"    - pricelist ≠ เรทเดือน")
                            print(f"    - value_18 = {value_16} - {total_rental_discount} = {value_18}")
                    else:
                        # มี end_x_date ที่ต่างกัน หรือ วันที่คืน > วันสิ้นสุด → คิดค่าเช่าส่วนต่างปกติ
                        print("\n  📍 SUB-CASE: มี end_x_date ที่ต่างกัน หรือ วันที่คืน > วันสิ้นสุด")
                        value_18 = value_16 - total_rental_discount
                        print(f"    - value_18 = {value_16} - {total_rental_discount} = {value_18}")
                else:
                    # ไม่พบ picking ก่อนหน้า → คิดปกติ
                    print("\n  📍 SUB-CASE: ไม่พบ picking ก่อนหน้า")
                    value_18 = value_16 - total_rental_discount
                    print(f"    - value_18 = {value_16} - {total_rental_discount} = {value_18}")

            # สรุปผล
            print("\n" + "-" * 60)
            print(f"✅ RESULT: value_18 = {value_18}")
            print("=" * 60 + "\n")

            # if prev_picking and prev_picking.end_x_date:
            #     # แปลง prev_end_x_date เป็น date object
            #     prev_end_x_date = prev_picking.end_x_date.date() if isinstance(prev_picking.end_x_date,
            #                                                                    datetime) else prev_picking.end_x_date
            #
            #     print(f"  - prev_end_x_date: {prev_end_x_date}")
            #     print(f"  - current end_x_date (ex): {ex}")
            #     print(f"  - prev_end_x_date == ex: {prev_end_x_date == ex}")
            #
            #     # เปรียบเทียบ end_x_date
            #     if prev_end_x_date == ex:
            #         print("\n  📍 SUB-CASE: วันสิ้นสุดเหมือนกัน")
            #
            #         # วันสิ้นสุดเหมือนกัน → ใช้ logic เรทเดือน
            #         if getattr(related_picking.sale_id.pricelist_id, 'name', '') == 'เรทเดือน':
            #             dd = (1 if (fx == sx) else (fx - sx).days)
            #             print(f"    - pricelist = เรทเดือน")
            #             print(f"    - dd (จำนวนวัน): {dd}")
            #
            #             if dd < 30:
            #                 value_18 = (0 - total_rental_discount)
            #                 print(f"    - dd < 30 → value_18 = 0 - {total_rental_discount} = {value_18}")
            #             else:
            #                 value_18 = (value_16 - total_rental_discount)
            #                 print(f"    - dd >= 30 → value_18 = {value_16} - {total_rental_discount} = {value_18}")
            #         else:
            #             value_18 = value_16 - total_rental_discount
            #             print(f"    - pricelist ≠ เรทเดือน")
            #             print(f"    - value_18 = {value_16} - {total_rental_discount} = {value_18}")
            #     else:
            #         # วันสิ้นสุดไม่เหมือนกัน → คิดค่าเช่าส่วนต่างปกติ
            #         print("\n  📍 SUB-CASE: วันสิ้นสุดไม่เหมือนกัน")
            #         value_18 = value_16 - total_rental_discount
            #         print(f"    - value_18 = {value_16} - {total_rental_discount} = {value_18}")
            # else:
            #     # ไม่พบ picking ก่อนหน้า → คิดปกติ
            #     print("\n  📍 SUB-CASE: ไม่พบ picking ก่อนหน้า หรือไม่มี end_x_date")
            #     value_18 = value_16 - total_rental_discount
            #     print(f"    - value_18 = {value_16} - {total_rental_discount} = {value_18}")

            # สรุปผล
            # print("\n" + "-" * 60)
            # print(f"✅ RESULT: value_18 = {value_18}")
            # print("=" * 60 + "\n")

            # เดบิตโน้ต L/D และส่วนลด
            # total_l = _to_float(sum(
            #     related_picking.sale_id.invoice_ids.mapped('debit_note_ids.invoice_line_ids')
            #     .filtered(lambda l: 'L' in l.analytic_tag_ids.mapped('name'))
            #     .mapped('price_subtotal_without_discount')
            # ) or 0.0)
            # total_d = _to_float(sum(
            #     related_picking.sale_id.invoice_ids.mapped('debit_note_ids.invoice_line_ids')
            #     .filtered(lambda l: 'D' in l.analytic_tag_ids.mapped('name'))
            #     .mapped('price_subtotal')
            # ) or 0.0)
            # สำหรับ total_l: กรอง reason_code_id.name == 'สินค้าหาย' และ state == 'posted'
            debit_notes_l = related_picking.sale_id.invoice_ids.mapped('debit_note_ids').filtered(
                lambda dn: dn.state == 'posted' and dn.reason_code_id and dn.reason_code_id.name == 'สินค้าหาย'
            )
            total_l = _to_float(sum(
                debit_notes_l.mapped('amount_total')
            ) or 0.0)

            # สำหรับ total_d: กรอง reason_code_id.name == 'สินค้าชำรุด' และ state == 'posted'
            debit_notes_d = related_picking.sale_id.invoice_ids.mapped('debit_note_ids').filtered(
                lambda dn: dn.state == 'posted' and dn.reason_code_id and dn.reason_code_id.name == 'สินค้าชำรุด'
            )
            total_d = _to_float(sum(
                debit_notes_d.mapped('amount_total')
            ) or 0.0)

            print("total_l (สินค้าหาย):", total_l)
            print("total_d (สินค้าชำรุด):", total_d)
            # discount_total_d = _to_float(sum(
            #     related_picking.sale_id.invoice_ids.mapped('debit_note_ids.invoice_line_ids.discount_amount')
            # ) or 0.0)

            discount_total_d = 0.0

            for debit_note in debit_notes_d:
                for line in debit_note.invoice_line_ids:
                    # ตรวจสอบว่า discount_method เป็น 'per'
                    if line.discount_method == 'per':
                        # คำนวณยอดลดจากเปอร์เซ็นต์
                        # discount_amount = เปอร์เซ็นต์
                        discount_value = ((line.quantity * line.price_unit) * line.discount_amount / 100)
                        discount_total_d += _to_float(discount_value)
                    else:
                        # ถ้าเป็นจำนวนเงินคงที่ให้บวกตรงๆ
                        discount_total_d += _to_float(line.discount_amount)

            discount_total_d = _to_float(discount_total_d or 0.0)

            print("discount_total_d (ยอดลดรวม):", discount_total_d)

            # สินค้า/บัญชี
            prod_dep = record.env['product.product'].search([('name', '=', "เงินประกันค่าเช่า")], limit=1)
            if not prod_dep:
                raise UserError(_("ไม่พบสินค้า '%s'") % "เงินประกันค่าเช่า")
            acc_dep = prod_dep.property_account_income_id.id or prod_dep.categ_id.property_account_income_categ_id.id
            if not acc_dep:
                raise UserError(_("สินค้า '%s' ยังไม่ได้ตั้งค่าบัญชีรายได้") % "เงินประกันค่าเช่า")

            # ปิดการใช้งาน ค่าเช่าเครื่องมือก่อสร้าง - เก็บไว้อ้างอิง
            # rent_label = "ค่าเช่าเครื่องมือก่อสร้าง"
            # prod_rent = record.env['product.product'].search([('name', '=', rent_label)], limit=1)
            # acc_rent = (
            #         prod_rent.property_account_income_id.id or prod_rent.categ_id.property_account_income_categ_id.id) if prod_rent else False

            # ล้างบรรทัดเดิม
            _remove_line(prod=prod_dep)
            # ปิดการใช้งาน ค่าเช่าเครื่องมือก่อสร้าง - เก็บไว้อ้างอิง
            # if prod_rent:
            #     _remove_line(prod=prod_rent)
            # else:
            #     _remove_line(prod=None, name=rent_label)

            # สูตรเก่า (ยังใช้บางกรณี)
            deposit_base = _to_float(pfb_amount - ((total_l + total_d) - discount_total_d))
            calculated_result = _to_float(pfb_amount - ((value_18 + total_l + total_d) - discount_total_d))

            # ยอดหนี้ค้างชำระรวม (สดจาก invoice_ids)
            total_outs = _to_float(
                sum(record.env['account.move'].browse(record.invoice_ids.ids).mapped('amount_residual')))

            # ✅ บวก outstanding เข้ากับ price_unit "เสมอ" ถ้า outstanding < price_unit (ไม่สน no_deduction)
            def add_outstanding(amount):
                """
                หักยอดค้างชำระที่เคยจ่ายไปแล้ว (snapshot) ออกจาก price_unit

                Logic:
                - ถ้ามี snapshot (เคยจ่ายไปแล้ว) → หักออก
                - ถ้าไม่มี snapshot → คืนค่าเดิม
                """
                snapshot = _to_float(record.outstanding_amount_snapshot)

                # ถ้ามี snapshot และ amount > 0 → หักออก
                if snapshot > 0 and amount > 0:
                    return amount - snapshot
                return amount

            # ---------- ตัดสินใจตามกติกา ----------
            if value_18 < 0:
                # บังคับ 2 รายการเสมอ
                dep_base = _to_float(pfb_amount) if record.no_deduction else deposit_base
                dep_amt = add_outstanding(dep_base)  # ← บวก outstanding ไม่ว่าสถานะติ๊ก
                if dep_amt != 0.0:
                    record.line_ids |= record.env['account.voucher.line'].new({
                        'product_id': prod_dep.id,
                        'name': prod_dep.name,
                        'quantity': 1.0,
                        'price_unit': dep_amt,
                        'account_id': acc_dep,
                    })
                # print("total_rental_discount", total_rental_discount)
                # print("value_18", value_18)
                # ปิดการใช้งาน ค่าเช่าเครื่องมือก่อสร้าง - เก็บไว้อ้างอิง
                # rent_amt = abs(_to_float(value_18))
                # if rent_amt >= 0.01:  # ถ้าน้อยกว่า 0.01 บาท ถือว่าเป็น 0
                #     if not prod_rent or not acc_rent:
                #         raise UserError(_("ไม่พบสินค้า/บัญชีสำหรับ '%s'") % rent_label)
                #     record.line_ids |= record.env['account.voucher.line'].new({
                #         'product_id': prod_rent.id,
                #         'name': prod_rent.name or rent_label,
                #         'quantity': 1.0,
                #         'price_unit': rent_amt,
                #         'account_id': acc_rent,
                #     })

            else:
                # 1 รายการ
                dep_base = _to_float(pfb_amount) if record.no_deduction else calculated_result
                dep_amt = add_outstanding(dep_base)  # ← บวก outstanding ไม่ว่าสถานะติ๊ก
                if dep_amt != 0.0:
                    record.line_ids |= record.env['account.voucher.line'].new({
                        'product_id': prod_dep.id,
                        'name': prod_dep.name,
                        'quantity': 1.0,
                        'price_unit': dep_amt,
                        'account_id': acc_dep,
                    })

    @api.depends('move_id.line_ids.reconciled', 'move_id.line_ids.account_id.internal_type')
    def _check_paid(self):
        self.paid = any(
            [((line.account_id.internal_type, 'in', ('receivable', 'payable')) and line.reconciled) for line in
             self.move_id.line_ids])

    def _get_currency(self):
        journal = self.env['account.journal'].browse(self.env.context.get('default_journal_id', False))
        if journal.currency_id:
            return journal.currency_id.id
        return self.env.user.company_id.currency_id.id

    def _get_company(self):
        return self.env.company

    @api.constrains('company_id', 'currency_id')
    def _check_company_id(self):
        for voucher in self:
            if not voucher.company_id:
                raise ValidationError(_("Missing Company"))
            if not voucher.currency_id:
                raise ValidationError(_("Missing Currency"))

    @api.depends('name', 'number')
    def name_get(self):
        return [(r.id, (r.number or _('Voucher'))) for r in self]

    @api.depends('journal_id', 'company_id')
    def _get_journal_currency(self):
        self.currency_id = self.journal_id.currency_id.id or self.company_id.currency_id.id

    def _get_tax_vals(self):
        for voucher in self:
            tax_vals = {}
            for line in voucher.line_ids:
                tax_info = line.tax_ids.compute_all(line.price_unit, voucher.currency_id, line.quantity,
                                                    line.product_id, voucher.partner_id)
                for t in tax_info.get('taxes', False):
                    tax_vals.setdefault(
                        t['id'], {"amount": 0.0, "base": 0.0, "account_id": "", "tax_repartition_line_id": ""}
                    )
                    tax_vals[t['id']]["account_id"] = t['account_id']
                    tax_vals[t['id']]["name"] = t['name']
                    tax_vals[t['id']]["tax_repartition_line_id"] = t['tax_repartition_line_id']
                    tax_vals[t['id']]["amount"] += t["amount"]
                    tax_vals[t['id']]["base"] += t["base"]
            return tax_vals

    @api.depends('tax_correction', 'line_ids.price_subtotal', 'wt_cert_ids')
    def _compute_total(self):
        tax_calculation_rounding_method = self.env.user.company_id.tax_calculation_rounding_method
        for voucher in self:
            total = 0
            tax_amount = 0
            tax_lines_vals_merged = {}

            for line in voucher.line_ids:
                tax_info = line.tax_ids.compute_all(line.price_unit, voucher.currency_id, line.quantity,
                                                    line.product_id, voucher.partner_id)
                if tax_calculation_rounding_method == 'round_globally':
                    total += tax_info.get('total_excluded', 0.0)
                    for t in tax_info.get('taxes', False):
                        key = (
                            t['id'],
                            t['account_id'],
                        )
                        if key not in tax_lines_vals_merged:
                            tax_lines_vals_merged[key] = t.get('amount', 0.0)
                        else:
                            tax_lines_vals_merged[key] += t.get('amount', 0.0)
                else:
                    total += tax_info.get('total_included', 0.0)
                    tax_amount += sum([t.get('amount', 0.0) for t in tax_info.get('taxes', False)])
            if tax_calculation_rounding_method == 'round_globally':
                tax_amount = sum([voucher.currency_id.round(t) for t in tax_lines_vals_merged.values()])
                voucher.amount = total + tax_amount + voucher.tax_correction
            else:
                voucher.amount = total + voucher.tax_correction
            voucher.tax_amount = tax_amount
            voucher.wht_amount = sum(line.tax_amount for line in voucher.wt_cert_ids)

    @api.onchange('date')
    def onchange_date(self):
        self.account_date = self.date

    @api.onchange('partner_id', 'pay_now')
    def onchange_partner_id(self):
        pay_journal_domain = [('type', 'in', ['cash', 'bank'])]
        if self.partner_id:
            self.account_id = self.partner_id.property_account_receivable_id \
                if self.voucher_type == 'sale' else self.partner_id.property_account_payable_id
        else:
            if self.voucher_type == 'purchase':
                pay_journal_domain.append(('outbound_payment_method_ids', '!=', False))
            else:
                pay_journal_domain.append(('inbound_payment_method_ids', '!=', False))
        return {'domain': {'payment_journal_id': pay_journal_domain}}

    refund_of_rental = fields.Boolean(
        string="Show refund_of_rental",
        compute="_compute_refund_of_rental",
        store=False
    )

    @api.depends()
    def _compute_refund_of_rental(self):
        for rec in self:
            rec.refund_of_rental = self.env.user.refund_of_rental
            print("rec.refund_of_rental", rec.refund_of_rental)

    def proforma_voucher(self):
        self.action_move_line_create()
        for record in self:
            if record.state == 'posted' and record.rental_return_select_id:
                # ดึง record ของ stock.picking และอัปเดตค่า
                picking = self.env['stock.picking'].browse(record.rental_return_select_id.id)
                if picking:
                    picking.write({'deposit_return_state': 'returned'})
                    print(f"Updated Picking ID: {picking.id} to 'returned'")

                if record.reference:
                    sale_order = self.env['sale.order'].search([('name', '=', record.reference)], limit=1)
                    if sale_order:
                        print("sale_order", sale_order.name)
                        sale_order.write({
                            'rental_status': 'done',
                            'check_state': 'done',
                        })

                        if sale_order.deposit_ref:
                            ref_names = sale_order.deposit_ref.split(',')

                            for ref_name in ref_names:
                                ref_name = ref_name.strip()  # ลบ space หรือ \n \r ที่อาจหลงมา

                                if not ref_name:
                                    continue  # ข้ามถ้าว่าง
                                # print("ref_name***", ref_name)
                                sale_order_deposit_ref = self.env['sale.order'].search([('name', '=', ref_name)],
                                                                                       limit=1)

                                if sale_order_deposit_ref:
                                    # print(f"[DepositRef] ✅ อัปเดตสถานะ SO: {ref_name}")
                                    sale_order_deposit_ref.sudo().write({
                                        'rental_status': 'done',
                                        'check_state': 'done',
                                    })

                                    picking_related = self.env['stock.picking'].search([
                                        ('group_id.name', '=', sale_order_deposit_ref.name),
                                        ('name', 'like', '%IN%')
                                    ], limit=1)

                                    if picking_related:
                                        # print("picking_related.group_id.id", picking_related.name)
                                        picking_related.write({'deposit_return_state': 'returned'})

                    else:
                        print("ไม่พบเอกสาร", record.reference)

    # account_voucher.py (แก้ไขเมธอด action_cancel_draft)

    def action_cancel_draft(self):
        """Set voucher กลับเป็น Draft, ยกเลิก Payment ที่เกี่ยวข้อง และเคลียร์ค่าอ้างอิง (รวม Snapshot)"""
        self.ensure_one()
        self.write({'state': 'draft'})

        # ----------------------------------------------------------------------
        # 1. จัดการ Payment ที่สร้างจาก voucher นี้ (payment_t_ids)
        # ----------------------------------------------------------------------
        payments_to_unlink = self.env['account.payment']

        if self.payment_t_ids:
            for payment in self.payment_t_ids:
                if not payment.exists():
                    self.message_post(
                        body=f"<p>⚠️ ข้ามการยกเลิก Payment ID: {payment.id} เนื่องจากถูกลบไปแล้ว.</p>"
                    )
                    continue

                try:
                    if payment.state == 'posted':
                        if payment.move_id and payment.move_id.exists():
                            reconciled_lines = payment.move_id.line_ids.filtered(lambda l: l.reconciled)
                            if reconciled_lines:
                                reconciled_lines.remove_move_reconcile()

                            payment.move_id.button_draft()
                            payment.move_id.button_cancel()
                            payment.move_id.with_context(force_delete=True).unlink()

                        if payment.exists():
                            payment.write({'state': 'draft'})
                            self.message_post(body=f"<p>ยกเลิกใบรับชำระ: <b>{payment.name}</b></p>")
                            payments_to_unlink |= payment

                except Exception as e:
                    self.message_post(
                        body=f"<p>❌ ไม่สามารถยกเลิก Payment {payment.name} (ID {payment.id}): {str(e)}</p>"
                    )

        # ลบ Payment ทั้งหมดที่ถูกยกเลิกสถานะแล้วออกจากระบบ
        if payments_to_unlink:
            payments_to_unlink.unlink()

        # ----------------------------------------------------------------------
        # 2. คืนค่า Snapshot และเคลียร์ความสัมพันธ์ใบแจ้งหนี้
        # ----------------------------------------------------------------------
        update_vals = {}

        # ✅ FIX: คืนค่า Snapshot กลับไปยัง total_outstanding และปรับ price_unit
        if self.outstanding_amount_snapshot > 0:
            snapshot = self.outstanding_amount_snapshot

            # คืนค่ายอดค้างชำระ
            update_vals['total_outstanding'] = snapshot
            update_vals['outstanding_amount_snapshot'] = 0.0

            # ✅ ปรับ price_unit ใน voucher lines (บวก Snapshot กลับเข้าไป)
            for line in self.line_ids:
                if line.price_unit != 0 and line.product_id.name == "เงินประกันค่าเช่า":
                    # บันทึกค่าเดิมก่อนแก้
                    old_price = line.price_unit

                    # คำนวณค่าใหม่ (บวก snapshot กลับ)
                    new_price = old_price + snapshot

                    # อัปเดตค่า
                    line.write({'price_unit': new_price})

                    # Log
                    self.message_post(
                        body=f"<p>🔄 ปรับ '{line.name}' จาก {old_price:,.2f} เป็น {new_price:,.2f} "
                             f"(คืนยอดค้างชำระ {snapshot:,.2f})</p>"
                    )

            # Log การคืนค่า Snapshot
            self.message_post(body=f"<p>✅ คืนค่ายอดค้างชำระรวม: {snapshot:,.2f} บาท</p>")

        # เคลียร์ความสัมพันธ์ทั้งหมด
        update_vals['invoice_ids'] = [(5, 0, 0)]  # เคลียร์ใบแจ้งหนี้ที่เลือก
        update_vals['invoice_ref_ids'] = [(5, 0, 0)]  # เคลียร์ใบแจ้งหนี้ประวัติ
        update_vals['payment_t_ids'] = [(5, 0, 0)]  # เคลียร์ความสัมพันธ์ Payment

        if update_vals:
            self.write(update_vals)

        self.message_post(body="<p>✅ เคลียร์ความสัมพันธ์หนี้ค้างชำระและใบรับชำระทั้งหมดเรียบร้อยแล้ว.</p>")

        # ----------------------------------------------------------------------
        # 3. โค้ดเดิมสำหรับ Picking และ Sale Order (UNCHANGED)
        # ----------------------------------------------------------------------
        for record in self:
            # ดึง record ของ stock.picking และอัปเดตค่า
            picking = self.env['stock.picking'].browse(record.rental_return_select_id.id)
            if picking and picking.exists():
                picking.write({'deposit_return_state': 'not_returned'})
                print(f"Updated Picking ID: {picking.id} to 'not_returned'")

            if record.reference:
                sale_order = self.env['sale.order'].search([('name', '=', record.reference)], limit=1)
                if sale_order:
                    if sale_order.deposit_ref:
                        ref_names = sale_order.deposit_ref.split(',')

                        for ref_name in ref_names:
                            ref_name = ref_name.strip()

                            if not ref_name:
                                continue

                            sale_order_deposit_ref = self.env['sale.order'].search([('name', '=', ref_name)], limit=1)

                            if sale_order_deposit_ref:
                                picking_related = self.env['stock.picking'].search([
                                    ('group_id.name', '=', sale_order_deposit_ref.name),
                                    ('name', 'like', '%IN%')
                                ], limit=1)

                                if picking_related:
                                    picking_related.write({'deposit_return_state': 'not_returned'})

        return True

    def cancel_voucher(self):
        for voucher in self:
            voucher.old_move_name = voucher.move_id.name
            voucher.move_id.button_cancel()
            voucher.move_id.unlink()
            voucher.message_post(body="<p><b>Cancel Receipts </b> </p>"
                                      "<p><b>Cancel Date:</b> %s </p>"
                                      "<p><b>Total:</b> %s </p>" % (
                                          datetime.today().strftime('%d/%m/%Y'), voucher.amount))
        self.write({'state': 'cancel', 'move_id': False})

    def unlink(self):
        for voucher in self:
            if voucher.state not in ('draft', 'cancel'):
                raise UserError(_('Cannot delete voucher(s) which are already opened or paid.'))
        return super(AccountVoucher, self).unlink()

    def first_move_line_get(self, move_id, company_currency, current_currency):
        debit = credit = 0.0
        amount = abs(self.amount - self.wht_amount)
        if self.voucher_type == 'purchase':
            # credit = self._convert(self.amount - self.wht_amount)
            if self.amount < 0:
                debit = amount
            else:
                credit = amount
        elif self.voucher_type == 'sale':
            # debit = self._convert(self.amount - self.wht_amount)
            if self.amount < 0:
                credit = amount
            else:
                debit = amount

        # if debit < 0.0: debit = 0.0
        # if credit < 0.0: credit = 0.0
        sign = debit - credit < 0 and -1 or 1
        # set the first line of the voucher

        move_line = {
            'name': self.payment_method_id.name or '/',
            'debit': debit,
            'credit': credit,
            'account_id': self.payment_method_id.account_id.id,
            'move_id': move_id,
            'journal_id': self.journal_id.id,
            'partner_id': self.partner_id.commercial_partner_id.id,
            'currency_id': company_currency != current_currency and current_currency or False,
            'amount_currency': (sign * abs(self.amount)  # amount < 0 for refunds
                                if company_currency != current_currency else 0.0),
            'date': self.account_date,
            'date_maturity': self.date_due,
        }
        return move_line

    def multi_move_line_get(self, move_id, company_currency, current_currency, payment_method_id, amount):
        debit = credit = 0.0
        # if self.voucher_type == 'purchase':
        #     credit = self._convert(amount)
        # elif self.voucher_type == 'sale':
        #     debit = self._convert(amount)
        # if debit < 0.0: debit = 0.0
        # if credit < 0.0: credit = 0.0

        # amount = abs(amount - self.wht_amount)
        if self.voucher_type == 'purchase':
            if amount < 0:
                debit = amount
            else:
                credit = amount
        elif self.voucher_type == 'sale':
            if amount < 0:
                credit = amount
            else:
                debit = amount
        sign = debit - credit < 0 and -1 or 1
        # set the first line of the voucher
        move_line = {
            'name': payment_method_id.name or '/',
            'debit': debit,
            'credit': abs(credit),
            'account_id': payment_method_id.account_id.id,
            'move_id': move_id,
            'journal_id': self.journal_id.id,
            'partner_id': self.partner_id.commercial_partner_id.id,
            'currency_id': company_currency != current_currency and current_currency or False,
            'amount_currency': (sign * abs(amount)
                                if company_currency != current_currency else 0.0),
            'date': self.account_date,
            'date_maturity': self.date_due,
        }
        return move_line

    def wht_move_line_get(self, move_id, company_currency, current_currency, wht_line):
        debit = credit = 0.0
        if self.voucher_type == 'purchase':
            credit = self._convert(wht_line.tax_amount)
        elif self.voucher_type == 'sale':
            debit = self._convert(wht_line.tax_amount)
        if debit < 0.0: debit = 0.0
        if credit < 0.0: credit = 0.0
        sign = debit - credit < 0 and -1 or 1
        wht_account_id = wht_line.account_id.id
        move_line = {
            'name': _('Withholding Tax'),
            'debit': debit,
            'credit': credit,
            'account_id': wht_account_id,
            'move_id': move_id,
            'journal_id': self.journal_id.id,
            'partner_id': self.partner_id.commercial_partner_id.id,
            'currency_id': company_currency != current_currency and current_currency or False,
            'amount_currency': (sign * abs(self.amount)  # amount < 0 for refunds
                                if company_currency != current_currency else 0.0),
            'date': self.account_date,
            'date_maturity': self.date_due,
        }
        return move_line

    def get_seq_voucher(self):
        if self.number:
            return self.number
        elif self.voucher_type == "sale":
            return self.env["ir.sequence"].next_by_code("sale.receipt", sequence_date=self.date)
        elif self.voucher_type == "purchase":
            return self.env["ir.sequence"].next_by_code("purchase.receipt", sequence_date=self.date)

    def account_move_get(self):

        move = {
            'journal_id': self.journal_id.id,
            'narration': self.narration,
            'date': self.account_date,
            'ref': self.reference,
            'voucher_id': self.id,
        }
        if self.old_move_name:
            move.update({
                'name': self.old_move_name,
                'sequence_generated': True
            })

        return move

    def _convert(self, amount):
        '''
        This function convert the amount given in company currency. It takes either the rate in the voucher (if the
        payment_rate_currency_id is relevant) either the rate encoded in the system.
        :param amount: float. The amount to convert
        :param voucher: id of the voucher on which we want the conversion
        :param context: to context to use for the conversion. It may contain the key 'date' set to the voucher date
            field in order to select the good rate to use.
        :return: the amount in the currency of the voucher's company
        :rtype: float
        '''
        for voucher in self:
            return voucher.currency_id._convert(amount, voucher.company_id.currency_id, voucher.company_id,
                                                voucher.account_date)

    def _create_tax_move(self, move_id, move_line_id, tax_line_id, tax_base=0.00, tax_amount=0.00):
        TaxInvoice = self.env["account.move.tax.invoice"]
        taxinv = TaxInvoice.create(
            {
                "move_id": move_id,
                "move_line_id": move_line_id.id,
                "voucher_id": self.id,
                "partner_id": self.partner_id.id,
                "tax_invoice_number": move_line_id.move_id.name,
                "tax_invoice_date": fields.Date.today() or False,
                "tax_base_amount": abs(tax_base),
                "balance": abs(tax_amount),
                'tax_line_id': tax_line_id,
            }
        )

    def voucher_move_line_create(self, line_total, move_id, company_currency, current_currency):
        '''
        Create one account move line, on the given account move, per voucher line where amount is not 0.0.
        It returns Tuple with tot_line what is total of difference between debit and credit and
        a list of lists with ids to be reconciled with this format (total_deb_cred,list_of_lists).

        :param voucher_id: Voucher id what we are working with
        :param line_total: Amount of the first line, which correspond to the amount we should totally split among all voucher lines.
        :param move_id: Account move wher those lines will be joined.
        :param company_currency: id of currency of the company to which the voucher belong
        :param current_currency: id of currency of the voucher
        :return: Tuple build as (remaining amount not allocated on voucher lines, list of account_move_line created in this method)
        :rtype: tuple(float, list of int)
        '''
        tax_calculation_rounding_method = self.env.user.company_id.tax_calculation_rounding_method
        tax_lines_vals = []
        for line in self.line_ids:

            # create one move line per voucher line where amount is not 0.0
            if not line.price_subtotal:
                continue
            line_subtotal = line.price_subtotal
            if self.voucher_type == 'sale':
                line_subtotal = -1 * line.price_subtotal
            credit = debit = 0
            if self.voucher_type == 'sale':
                if line.price_subtotal < 0:
                    debit = abs(line_subtotal)
                else:
                    credit = abs(line_subtotal)
            else:
                if line.price_subtotal < 0:
                    credit = abs(line_subtotal)
                else:
                    debit = abs(line_subtotal)

            move_line = {
                'journal_id': self.journal_id.id,
                'name': line.name or '/',
                'account_id': line.account_id.id,
                'move_id': move_id,
                'quantity': line.quantity,
                'product_id': line.product_id.id,
                'partner_id': self.partner_id.commercial_partner_id.id,
                'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
                'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
                'credit': credit,
                'debit': debit,
                'date': self.account_date,
                'tax_ids': [(4, t.id) for t in line.tax_ids],
                'amount_currency': line_subtotal if current_currency != company_currency else 0.0,
                'currency_id': company_currency != current_currency and current_currency or False,
                'payment_id': self._context.get('payment_id'),
            }
            self.env['account.move.line'].create(move_line)
        return line_total

    def vat_move_line_create(self, move_id, company_currency, current_currency):
        tax_vals = self._get_tax_vals()
        Currency = self.env['res.currency']
        company_cur = Currency.browse(company_currency)
        current_cur = Currency.browse(current_currency)
        for tax in tax_vals:
            temp = {
                'account_id': tax_vals[tax]['account_id'],
                'name': tax_vals[tax]['name'],
                'tax_line_id': tax,
                'move_id': move_id,
                'date': self.account_date,
                'partner_id': self.partner_id.id,
                'debit': self.voucher_type != 'sale' and tax_vals[tax]['amount'] or 0.0,
                'credit': self.voucher_type == 'sale' and tax_vals[tax]['amount'] or 0.0,
            }
            if company_currency != current_currency:
                ctx = {}
                sign = temp['credit'] and -1 or 1
                amount_currency = company_cur._convert(tax_vals[tax]['amount'], current_cur, self.company_id,
                                                       self.account_date or fields.Date.today(), round=True)
                if self.account_date:
                    ctx['date'] = self.account_date
                temp['currency_id'] = current_currency
                temp['amount_currency'] = sign * abs(amount_currency)

            move_line_id = self.env['account.move.line'].create(temp)
            self._create_tax_move(move_id, move_line_id, tax, tax_vals[tax]['base'], tax_vals[tax]['amount'])
            move_line_id.update({'tax_repartition_line_id': tax_vals[tax]['tax_repartition_line_id']})

    def action_move_line_create(self):
        '''
        Confirm the vouchers given in ids and create the journal entries for each of them
        '''
        for voucher in self:
            local_context = dict(self._context)
            if voucher.move_id:
                continue
            company_currency = voucher.journal_id.company_id.currency_id.id
            current_currency = voucher.currency_id.id or company_currency
            # we select the context to use accordingly if it's a multicurrency case or not
            # But for the operations made by _convert, we always need to give the date in the context
            ctx = local_context.copy()
            ctx['date'] = voucher.account_date
            ctx['check_move_validity'] = False
            # Create the account move record.
            move = self.env['account.move'].create(voucher.account_move_get())
            # Get the name of the account_move just created
            # Create the first line of the voucher
            if voucher.is_payment_multi is False:
                move_line = self.env['account.move.line'].with_context(ctx).create(
                    voucher.with_context(ctx).first_move_line_get(move.id, company_currency, current_currency))
            else:
                for payment in voucher.payment_ids:
                    move_line = self.env['account.move.line'].with_context(ctx).create(
                        voucher.with_context(ctx).multi_move_line_get(move.id, company_currency, current_currency,
                                                                      payment.payment_method_id, payment.total))
            line_total = move_line.debit - move_line.credit
            if voucher.voucher_type == 'sale':
                line_total = line_total - voucher._convert(voucher.tax_amount)
            elif voucher.voucher_type == 'purchase':
                line_total = line_total + voucher._convert(voucher.tax_amount)

            # MEMO Create move line with wht certificate
            for wht_line in self.wt_cert_ids:
                move_line = self.env['account.move.line'].with_context(ctx).create(
                    voucher.with_context(ctx).wht_move_line_get(move.id, company_currency, current_currency, wht_line))

            # Create one move line per voucher line where amount is not 0.0
            line_total = voucher.with_context(ctx).voucher_move_line_create(line_total, move.id, company_currency,
                                                                            current_currency)
            # Create move line vat
            voucher.with_context(ctx).vat_move_line_create(move.id, company_currency, current_currency)

            # Create a payment to allow the reconciliation when pay_now = 'pay_now'.
            # if voucher.pay_now == 'pay_now':

            # payment_id = (self.env['account.payment']
            #     .with_context(force_counterpart_account=voucher.account_id.id)
            #     .create(voucher.voucher_pay_now_payment_create()))
            # payment_id.post()

            # Reconcile the receipt with the payment
            # lines_to_reconcile = (payment_id.move_line_ids + move.line_ids).filtered(lambda l: l.account_id == voucher.account_id)
            # lines_to_reconcile.reconcile()

            # Add tax correction to move line if any tax correction specified
            if voucher.tax_correction != 0.0:
                tax_move_line = self.env['account.move.line'].search(
                    [('move_id', '=', move.id), ('tax_line_id', '!=', False)], limit=1)
                if len(tax_move_line):
                    tax_move_line.write(
                        {'debit': tax_move_line.debit + voucher.tax_correction if tax_move_line.debit > 0 else 0,
                         'credit': tax_move_line.credit + voucher.tax_correction if tax_move_line.credit > 0 else 0})

            # We post the voucher.
            voucher.write({
                'move_id': move.id,
                'state': 'posted',
                'number': self.get_seq_voucher()
            })
            move.post()
        return True

    def _track_subtype(self, init_values):
        if 'state' in init_values:
            mail = self.env.ref('account_voucher.mt_voucher_state_change')
            return self.env.ref('account_voucher.mt_voucher_state_change')
        return super(AccountVoucher, self)._track_subtype(init_values)


class AccountVoucherLine(models.Model):
    _name = 'account.voucher.line'
    _description = 'Accounting Voucher Line'

    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(default=10,
                              help="Gives the sequence of this line when displaying the voucher.")
    voucher_id = fields.Many2one('account.voucher', 'Voucher', required=1, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product',
                                 ondelete='set null', index=True)
    account_id = fields.Many2one('account.account', string='Account',
                                 required=True, domain=[('deprecated', '=', False)],
                                 help="The income or expense account related to the selected product.")
    price_unit = fields.Float(
        string='Unit Price',
        required=True,
        digits=dp.get_precision('Product Price'),
        oldname='amount'
    )
    price_subtotal = fields.Monetary(string='Amount',
                                     store=True, readonly=True, compute='_compute_subtotal')
    quantity = fields.Float(digits=dp.get_precision('Product Unit of Measure'),
                            required=True, default=1)
    account_analytic_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    company_id = fields.Many2one('res.company', related='voucher_id.company_id', string='Company', store=True,
                                 readonly=True)
    tax_ids = fields.Many2many('account.tax', string='Tax', help="Only for tax excluded from price")
    currency_id = fields.Many2one('res.currency', related='voucher_id.currency_id', readonly=False)
    wht_total = fields.Float(string="Withholding Tax", required=False, digits=dp.get_precision('Product Price'))

    can_edit_voucher = fields.Boolean(
        string="Can Edit Voucher",
        compute="_compute_can_edit_voucher",
        store=False
    )

    def _compute_can_edit_voucher(self):
        for rec in self:
            rec.can_edit_voucher = self.env.user.can_edit_voucher_lines

    @api.depends('price_unit', 'tax_ids', 'quantity', 'product_id', 'voucher_id.currency_id')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
            if line.tax_ids:
                taxes = line.tax_ids.compute_all(line.price_unit, line.voucher_id.currency_id, line.quantity,
                                                 product=line.product_id, partner=line.voucher_id.partner_id)
                line.price_subtotal = taxes['total_excluded']

    @api.onchange('product_id', 'voucher_id', 'price_unit', 'company_id')
    def _onchange_line_details(self):
        if not self.voucher_id or not self.product_id or not self.voucher_id.partner_id:
            return
        onchange_res = self.product_id_change(
            self.product_id.id,
            self.voucher_id.partner_id.id,
            self.price_unit,
            self.company_id.id,
            self.voucher_id.currency_id.id,
            self.voucher_id.voucher_type)
        for fname, fvalue in onchange_res['value'].items():
            setattr(self, fname, fvalue)

    def _get_account(self, product, fpos, type):
        accounts = product.product_tmpl_id.get_product_accounts(fpos)
        if type == 'sale':
            return accounts['income']
        return accounts['expense']

    def product_id_change(self, product_id, partner_id=False, price_unit=False, company_id=None, currency_id=None,
                          type=None):
        # TDE note: mix of old and new onchange badly written in 9, multi but does not use record set
        context = self._context
        company_id = company_id if company_id is not None else context.get('company_id', False)
        company = self.env['res.company'].browse(company_id)
        currency = self.env['res.currency'].browse(currency_id)
        if not partner_id:
            raise UserError(_("You must first select a partner."))
        part = self.env['res.partner'].browse(partner_id)
        if part.lang:
            self = self.with_context(lang=part.lang)

        product = self.env['product.product'].browse(product_id)
        fpos = part.property_account_position_id
        account = self._get_account(product, fpos, type)
        values = {
            'name': product.partner_ref,
            'account_id': account.id,
        }

        if type == 'purchase':
            values['price_unit'] = price_unit or product.standard_price
            taxes = product.supplier_taxes_id or account.tax_ids
            if product.description_purchase:
                values['name'] += '\n' + product.description_purchase
        else:
            values['price_unit'] = price_unit or product.lst_price
            taxes = product.taxes_id or account.tax_ids
            if product.description_sale:
                values['name'] += '\n' + product.description_sale

        values['tax_ids'] = taxes.ids

        if company and currency:
            if company.currency_id != currency:
                if type == 'purchase':
                    values['price_unit'] = price_unit or product.standard_price
                values['price_unit'] = values['price_unit'] * currency.rate

        return {'value': values, 'domain': {}}


class AccountVoucherPayment(models.Model):
    _name = 'account.voucher.payment'
    _rec_name = 'ref'
    _description = 'New Description'

    voucher_id = fields.Many2one("account.voucher", string="Payment", ondelete="cascade")
    company_id = fields.Many2one('res.company', related='voucher_id.company_id', string='Company', store=True,
                                 readonly=True)

    payment_method_id = fields.Many2one("payment.method", string="Payment Method",
                                        required=True)
    bank_account_id = fields.Many2one(
        "res.partner.bank", string="Bank Account"
    )
    account_id = fields.Many2one("account.account", related='payment_method_id.account_id', string="Account")
    cheque_id = fields.Many2one("account.cheque", string="Cheque", domain="[('state', '=', 'draft')]")
    total = fields.Float(string="Total", digits=(36, 2), required=True)
    ref = fields.Char(string="Ref", required=False, )
    type = fields.Selection(
        'Payment method',
        related='payment_method_id.type',
        required=False
    )


class WithholdingTaxCert(models.Model):
    _inherit = "withholding.tax.cert"

    voucher_id = fields.Many2one('account.voucher', string='Account Voucher', ondelete="cascade", )


class AccountMoveTaxInvoice(models.Model):
    _inherit = "account.move.tax.invoice"

    voucher_id = fields.Many2one('account.voucher', string='Account Voucher', ondelete="cascade", )


class AccountCheque(models.Model):
    _inherit = "account.cheque"

    voucher_id = fields.Many2one("account.voucher", string="Sale/Purchase", compute='_compute_voucher_id')

    def _compute_voucher_id(self):
        for cheque in self:
            voucher_id = cheque.voucher_id.search([('cheque_id', '=', cheque.id)], limit=1)
            voucher_line_ids = self.env['account.voucher.payment'].search([('cheque_id', '=', cheque.id)])
            for voucher_line in voucher_line_ids:
                voucher_id = voucher_line.voucher_id
            cheque.voucher_id = voucher_id


class AccountMove(models.Model):
    _inherit = "account.move"

    voucher_id = fields.Many2one('account.voucher', string='Account Voucher', ondelete="cascade", readonly=True)