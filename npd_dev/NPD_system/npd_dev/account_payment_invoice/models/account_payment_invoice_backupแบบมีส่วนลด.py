# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    search_invoice_name = fields.Char(string="เลขใบแจ้งหนี้")

    invoice_ids = fields.One2many(
        "account.payment.invoice", "payment_id", string="Invoice List"
    )
    paid_ids = fields.One2many(
        "account.paid.line", "payment_id", string="Payment Method"
    )
    paid_amount = fields.Float(string="Paid Amount", compute="_compute_paid_amount")
    payment_amount = fields.Float(string="Amount", compute="_compute_paid_amount")
    wht_amount = fields.Float(string='Withholding Tax',compute='_compute_paid_amount')
    wht_base_amount = fields.Float(string='Wht Base',compute='_compute_paid_amount')
    wt_cert_ids = fields.One2many(
        comodel_name="withholding.tax.cert",
        inverse_name="payment_id",
        string="Withholding Tax Cert.",
        readonly=False,
    )
    is_payment_multi = fields.Boolean(string='Payment Multi', default=False)
    payment_method_one_id = fields.Many2one("payment.method",
                                            string="Payment Method",
                                            domain="[('type', 'in', ['cash','bank','cheque']),('is_active','=',True)]")
    cheque_id = fields.Many2one("account.cheque", string="Cheque",
                                domain="[('state', '=', 'draft')]")
    type = fields.Selection(
        'Payment method',
        related='payment_method_one_id.type',
        required=True
    )

    payment_account_id = fields.Many2one("account.account", related='payment_method_one_id.account_id', string="Account")
    available_partner_bank_ids = fields.Many2many('res.partner.bank',readonly=True)
    amount_currency = fields.Float(
        string="Currency Amount",
        store=True,
        compute='_compute_amount_currency',
        required=False,
    )
    is_multi_currency = fields.Boolean(
        string="Currency",
        store=True,
        compute='_get_currency_company'
    )

    write_off_amount = fields.Float(
        string="WriteOff Amount",
        store=True,
        compute='_compute_write_off_amount',
        required=False,
    )
    total_amount = fields.Float(
        string="Total Amount",
        store=True,
        compute='_compute_paid_amount',
        required=False,
    )

    cash_status = fields.Selection([
        ('returned', 'โอนคืนแล้ว')
    ], string='สถานะเงินสด', default=False)

    overpaid_refund_status = fields.Selection([
        ('overpaid_refund', 'เสร็จสิ้น')
    ], string='สถานะคืนเงินโอนเกิน', default=False)

    wtax_refund_status = fields.Selection([
        ('wtax_refund', 'เสร็จสิ้น')
    ], string='สถานะคืนหัก ณ ที่จ่าย', default=False)

    rental_difference_status = fields.Selection([
        ('rental_difference', 'เสร็จสิ้น')
    ], string='สถานะโอนคืนค่าเช่าส่วนต่าง', default=False)

    cash_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Cash Invoice Ref",
        required=False,
    )

    voucher_source_id = fields.Many2one(
        'account.voucher',
        string='สร้างจากใบรับชำระค้างชำระ',
        help='ชี้กลับไปยังใบรับชำระ (Voucher) ที่กดสร้างรายการนี้'
    )

    # แก้ไข: เปลี่ยนจาก default เป็น compute และไม่เก็บค่า (store=False)
    can_edit_date = fields.Boolean(
        string='Can Edit Date',
        compute='_compute_can_edit_date',
        store=False,  # ไม่เก็บค่าในฐานข้อมูล
    )

    @api.depends('state', 'company_id')  # ใส่ dependency เพื่อช่วยกระตุ้นการคำนวณเมื่อฟอร์มโหลด/เปลี่ยน context
    def _compute_can_edit_date(self):
        # ใช้ self.env.user เพื่อตรวจสอบสิทธิ์ของผู้ใช้งานปัจจุบัน
        is_allowed = bool(self.env.user.account_payment_lock_draft_date)
        for payment in self:
            payment.can_edit_date = is_allowed

    @api.depends('paid_ids')
    def _compute_write_off_amount(self):
        for payment in self:
            payment.write_off_amount = sum([line.is_write_off and line.total or 0 for line in payment.paid_ids])



    @api.depends('currency_id')
    def _get_currency_company(self):
        for payment in self:
            if payment.company_id.currency_id.id == payment.currency_id.id:
                payment.is_multi_currency = False
            else:
                payment.is_multi_currency = True
                payment.is_payment_multi = False

    @api.depends('amount', 'currency_id')
    def _compute_amount_currency(self):
        for payment in self:
            if payment.company_id and payment.currency_id != payment.company_id.currency_id:
                payment.amount_currency = payment.currency_id._convert(
                        payment.amount,
                        payment.company_id.currency_id,
                        payment.company_id,
                        payment.date or fields.Date.context_today(self),
                        )
            else:
                payment.amount_currency = payment.amount

    def write(self, vals):
        # OVERRIDE
        res = super().write(vals)
        self._synchronize_to_moves(set(vals.keys()))
        return res

    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        currency_id = self.currency_id.id
        line_vals_list = []

        if self.payment_type == 'inbound':
            liquidity_amount_currency = self.amount
        elif self.payment_type == 'outbound':
            liquidity_amount_currency = -self.amount
        else:
            liquidity_amount_currency = 0.0

        if self.invoice_ids or self.amount != 0:

            # 1. Bank/Cash line (ยอดรับชำระจริง)
            if self.paid_ids and self.is_payment_multi:
                # Multiple payment methods
                for paid in self.paid_ids:
                    liquidity_balance = self.payment_type == 'inbound' and paid.total or -paid.total
                    line_vals_list.append({
                        "name": paid.payment_method_id.name,
                        "date_maturity": self.date,
                        "amount_currency": liquidity_amount_currency,
                        "currency_id": currency_id,
                        "debit": liquidity_balance if liquidity_balance > 0.0 else 0.0,
                        "credit": -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                        "partner_id": self.partner_id.id,
                        "account_id": paid.account_id.id,
                        "analytic_account_id": paid.analytic_account_id.id or None,
                        "analytic_tag_ids": [(6, 0, paid.analytic_tag_ids.ids)] or None,
                    })
            else:
                # Single payment method
                payment_amount = self.currency_id == self.company_id.currency_id \
                                 and self.amount \
                                 or self.amount_currency
                liquidity_balance = self.payment_type == 'inbound' and payment_amount or -payment_amount
                liquidity_currency = self.payment_type == 'inbound' and self.amount or -self.amount

                line_vals_list.append({
                    "name": self.payment_method_one_id.name,
                    "date_maturity": self.date,
                    "amount_currency": liquidity_currency,
                    "currency_id": currency_id,
                    "debit": liquidity_balance if liquidity_balance > 0.0 else 0.0,
                    "credit": -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                    "partner_id": self.partner_id.id,
                    "account_id": self.payment_account_id.id,
                })

            # 2. Withholding Tax (ถ้ามี)
            for wht_line in self.wt_cert_ids:
                wt_amount = self.payment_type == 'inbound' and wht_line.tax_amount or -wht_line.tax_amount
                wht_account_id = wht_line.account_id.id
                if not wht_account_id:
                    raise UserError(_("Not account withholding tax please config."))

                line_vals_list.append({
                    "name": "Withholding Tax " + wht_line.income_tax_form,
                    "date_maturity": self.date,
                    "amount_currency": wt_amount,
                    "currency_id": currency_id,
                    "debit": wt_amount if wt_amount > 0.0 else 0.0,
                    "credit": -wt_amount if wt_amount < 0.0 else 0.0,
                    "partner_id": self.partner_id.id,
                    "account_id": wht_account_id,
                })

            # 3. คำนวณส่วนลดทั้งหมด
            total_discount = 0
            for invoice_list in self.invoice_ids:
                invoice = invoice_list.invoice_id

                # คำนวณส่วนลดของ invoice นี้
                invoice_discount = 0
                if hasattr(invoice, 'amount_discount') and invoice.amount_discount > 0:
                    invoice_discount = invoice.amount_discount
                else:
                    for inv_line in invoice.invoice_line_ids:
                        if hasattr(inv_line, 'discount_amount') and inv_line.discount_amount > 0:
                            invoice_discount += inv_line.discount_amount
                        elif hasattr(inv_line, 'discount') and inv_line.discount > 0:
                            line_discount = (inv_line.price_unit * inv_line.quantity * inv_line.discount / 100)
                            invoice_discount += line_discount

                total_discount += invoice_discount

            # 4. สร้าง Discount line (ถ้ามีส่วนลด)
            if total_discount > 0:
                discount_account = self.env['account.account'].search([
                    ('code', '=', '4210-03'),
                    ('company_id', '=', self.company_id.id)
                ], limit=1)

                if not discount_account:
                    discount_account = self.env['account.account'].search([
                        ('name', 'ilike', 'ส่วนลด'),
                        ('user_type_id.type', '=', 'income'),
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)

                if discount_account:
                    if self.payment_type == 'inbound':
                        # ส่วนลดขาย - Dr. Discount
                        line_vals_list.append({
                            "name": f"ส่วนลด",
                            "date_maturity": self.date,
                            "amount_currency": total_discount,
                            "currency_id": currency_id,
                            "debit": total_discount,
                            "credit": 0.0,
                            "partner_id": self.partner_id.id,
                            "account_id": discount_account.id,
                        })

            # 5. Receivable/Payable lines
            for invoice_list in self.invoice_ids:
                invoice = invoice_list.invoice_id

                # ใช้ paid_total + ส่วนลดของ invoice นี้
                invoice_discount = 0
                if hasattr(invoice, 'amount_discount') and invoice.amount_discount > 0:
                    invoice_discount = invoice.amount_discount
                else:
                    for inv_line in invoice.invoice_line_ids:
                        if hasattr(inv_line, 'discount_amount') and inv_line.discount_amount > 0:
                            invoice_discount += inv_line.discount_amount
                        elif hasattr(inv_line, 'discount') and inv_line.discount > 0:
                            line_discount = (inv_line.price_unit * inv_line.quantity * inv_line.discount / 100)
                            invoice_discount += line_discount

                # Receivable = ยอดชำระ + ส่วนลด
                invoice_total = invoice_list.paid_total + invoice_discount

                if self.payment_type == "inbound":
                    counterpart_balance = -invoice_total
                    name = "Receive Invoice " + invoice.name
                    amount_currency = -invoice_total
                else:
                    counterpart_balance = invoice_total
                    name = "Payment Invoice " + invoice.name
                    amount_currency = invoice_total

                if counterpart_balance != 0:
                    line_vals_list.append({
                        "name": _(name) or "",
                        "date_maturity": self.date,
                        "amount_currency": amount_currency,
                        "currency_id": currency_id,
                        "debit": counterpart_balance if counterpart_balance > 0.0 else 0.0,
                        "credit": -counterpart_balance if counterpart_balance < 0.0 else 0.0,
                        "partner_id": self.partner_id.id,
                        "account_id": self.destination_account_id.id,
                        "invoice_id": invoice.id,
                    })

        else:
            raise UserError(_("Customer/Vendor is not invoice cannot Save data!!"))

        # Debug - ตรวจสอบ balance
        total_debit = sum(line['debit'] for line in line_vals_list)
        total_credit = sum(line['credit'] for line in line_vals_list)
        _logger.info(f"""
        ===== Journal Entry Debug =====
        Payment: {self.name}
        Total Debit: {total_debit}
        Total Credit: {total_credit}
        Difference: {total_debit - total_credit}
        Lines:
        """)
        for line in line_vals_list:
            _logger.info(f"  {line['name']}: Dr={line['debit']} Cr={line['credit']}")
        _logger.info("=" * 30)

        return line_vals_list

    def _synchronize_from_moves(self, changed_fields):
        """Update the account.payment regarding its related account.move.
        Also, check both models are still consistent.
        :param changed_fields: A set containing all modified fields on account.move.
        """
        if self._context.get("skip_account_move_synchronization"):
            return

        for pay in self.with_context(skip_account_move_synchronization=True):

            # After the migration to 14.0, the journal entry could be shared between the account.payment and the
            # account.bank.statement.line. In that case, the synchronization will only be made with the statement line.
            if pay.move_id.statement_line_id:
                continue

            move = pay.move_id
            move_vals_to_write = {}
            payment_vals_to_write = {}

            if "journal_id" in changed_fields:
                if pay.journal_id.type not in ("bank", "cash"):
                    raise UserError(
                        _("A payment must always belongs to a bank or cash journal.")
                    )

            if "line_ids" in changed_fields:
                all_lines = move.line_ids
                (
                    liquidity_lines,
                    counterpart_lines,
                    writeoff_lines,
                ) = pay._seek_for_lines()

                # if len(liquidity_lines) != 1 or len(counterpart_lines) != 1:
                #     raise UserError(_(
                #         "The journal entry %s reached an invalid state relative to its payment.\n"
                #         "To be consistent, the journal entry must always contains:\n"
                #         "- one journal item involving the outstanding payment/receipts account.\n"
                #         "- one journal item involving a receivable/payable account.\n"
                #         "- optional journal items, all sharing the same account.\n\n"
                #     ) % move.display_name)

                # if writeoff_lines and len(writeoff_lines.account_id) != 1:
                #     raise UserError(
                #         _(
                #             "The journal entry %s reached an invalid state relative to its payment.\n"
                #             "To be consistent, all the write-off journal items must share the same account."
                #         )
                #         % move.display_name
                #     )

                # if any(
                #     line.currency_id != all_lines[0].currency_id for line in all_lines
                # ):
                #     raise UserError(
                #         _(
                #             "The journal entry %s reached an invalid state relative to its payment.\n"
                #             "To be consistent, the journal items must share the same currency."
                #         )
                #         % move.display_name
                #     )

                # if any(
                #     line.partner_id != all_lines[0].partner_id for line in all_lines
                # ):
                #     raise UserError(
                #         _(
                #             "The journal entry %s reached an invalid state relative to its payment.\n"
                #             "To be consistent, the journal items must share the same partner."
                #         )
                #         % move.display_name
                #     )

                if counterpart_lines.account_id.user_type_id.type == "receivable":
                    partner_type = "customer"
                else:
                    partner_type = "supplier"
                #Check liquidity_lines is not value to update
                if liquidity_lines:
                    liquidity_amount = liquidity_lines.amount_currency

                    move_vals_to_write.update(
                        {
                            "currency_id": liquidity_lines.currency_id.id,
                            "partner_id": liquidity_lines.partner_id.id,
                        }
                    )

                    payment_vals_to_write.update(
                        {
                            "amount": abs(liquidity_amount),
                            "partner_type": partner_type,
                            "currency_id": liquidity_lines.currency_id.id,
                            "destination_account_id": counterpart_lines.account_id.id,
                            "partner_id": liquidity_lines.partner_id.id,
                        }
                    )

                    if liquidity_amount > 0.0:
                        payment_vals_to_write.update({"payment_type": "inbound"})
                    elif liquidity_amount < 0.0:
                        payment_vals_to_write.update({"payment_type": "outbound"})

            move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
            pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))

    def _synchronize_to_moves(self, changed_fields):
        """Update the account.move regarding the modified account.payment.
        :param changed_fields: A list containing all modified fields on account.payment.
        """
        if self._context.get("skip_account_move_synchronization"):
            return
        #Add paid_ids and invoice_ids create move line
        if not any(
            field_name in changed_fields
            for field_name in (
                "date",
                "amount",
                "payment_type",
                "partner_type",
                "payment_reference",
                "is_internal_transfer",
                "currency_id",
                "partner_id",
                "destination_account_id",
                "partner_bank_id",
                "paid_ids",
                "invoice_ids",
                "is_payment_multi",
                "payment_method_one_id",
                "wt_cert_ids",
            )
        ):
            return

        for pay in self.with_context(skip_account_move_synchronization=True):
            liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

            # Make sure to preserve the write-off amount.
            # This allows to create a new payment with custom 'line_ids'.

            if writeoff_lines:
                counterpart_amount = sum(counterpart_lines.mapped("amount_currency"))
                writeoff_amount = sum(writeoff_lines.mapped("amount_currency"))

                # To be consistent with the payment_difference made in account.payment.register,
                # 'writeoff_amount' needs to be signed regarding the 'amount' field before the write.
                # Since the write is already done at this point, we need to base the computation on accounting values.
                if (counterpart_amount > 0.0) == (writeoff_amount > 0.0):
                    sign = -1
                else:
                    sign = 1
                writeoff_amount = abs(writeoff_amount) * sign

                write_off_line_vals = {
                    "name": writeoff_lines[0].name,
                    "amount": writeoff_amount,
                    "account_id": writeoff_lines[0].account_id.id,
                }
            else:
                write_off_line_vals = {}

            line_vals_list = pay._prepare_move_line_default_vals(
                write_off_line_vals=write_off_line_vals
            )
            line_ids_commands = []
            for li in line_vals_list:
                line_ids_commands.append((0, 0, li))
            # * Remove line_ids create move line
            # line_ids_commands = [
            #     (1, liquidity_lines.id, line_vals_list[0]),
            #     (1, counterpart_lines.id, line_vals_list[1]),
            # ]

            # for line in writeoff_lines:
            #     line_ids_commands.append((2, line.id))

            # for extra_line_vals in line_vals_list[2:]:
            #     line_ids_commands.append((0, 0, extra_line_vals))

            # Update the existing journal items.
            # If dealing with multiple write-off lines, they are dropped and a new one is generated.
            pay.move_id.write({"line_ids": False})
            pay.move_id.write(
                {
                    "partner_id": pay.partner_id.id,
                    "currency_id": pay.currency_id.id,
                    "partner_bank_id": pay.partner_bank_id.id,
                    "line_ids": line_ids_commands,
                }
            )

    @api.depends("invoice_ids.paid_total", "paid_ids", "wt_cert_ids")
    def _compute_paid_amount(self):
        for payment in self:
            payment.paid_amount = sum([line.paid_total for line in payment.invoice_ids])
            payment.wht_base_amount = sum([line.paid_total > 0 and line.wht_base or 0 for line in payment.invoice_ids])
            payment.wht_amount = sum([line.tax_amount or 0 for line in payment.wt_cert_ids])
            # payment_total = sum([line.total or 0 for line in payment.paid_ids])
            payment.payment_amount = payment.amount - payment.wht_amount
            payment.total_amount = payment.paid_amount - payment.wht_amount - payment.write_off_amount

    @api.onchange("paid_ids")
    def _onchange_paid_ids(self):
        total = 0
        for line in self.paid_ids:
            total += line.total
        self.amount = total

    @api.onchange('paid_amount','wht_amount')
    def _onchange_paid_amount(self):
        self.amount = self.paid_amount - self.wht_amount


    # def action_post(self):
    #     """draft -> posted"""
    #
    #     #* Check invoice paid total is zero to remove
    #     if not self.invoice_ids:
    #         raise UserError(_("Not Invoice line to confirm payment."))
    #     if self.amount == 0 or self.paid_amount == 0:
    #         raise UserError(_("Invoice amount or Payment amount is zero please invoice Paid Total and Payment Total"))
    #     for line in self.invoice_ids:
    #         if line.paid_total == 0:
    #             line.sudo().unlink()
    #
    #     self.move_id._post(soft=False)
    #
    #     # npd******************************************************************************
    #     if self.move_id.state == "posted":
    #         self.group_account_tax_invoice()
    #         self.cheque_assigned()
    #     else:
    #         self._reconcile_payment()
    #         self.group_account_tax_invoice()
    #         self.cheque_assigned()
    #
    #     # npd******************************************************************************

    def action_post(self):
        """draft -> posted"""
        #* Check invoice paid total is zero to remove

        if not self.invoice_ids:
            raise UserError(_("Not Invoice line to confirm payment."))
        if self.amount == 0 or self.paid_amount == 0:
            raise UserError(_("Invoice amount or Payment amount is zero please invoice Paid Total and Payment Total"))
        for line in self.invoice_ids:
            if line.paid_total == 0:
                line.sudo().unlink()

        self.move_id._post(soft=False)
        self._reconcile_payment()
        self.group_account_tax_invoice()
        self.cheque_assigned()
        # self.action_rework_reverse_move()
        self.update_voucher_with_payment()

        today = fields.Date.today()
        #  อัปเดต rental_status ของ Sale Order ถ้า invoice ชำระแล้วทั้งหมด
        for invoice_line in self.invoice_ids:
            invoice = invoice_line.invoice_id
            if invoice.payment_state == 'paid' and invoice.invoice_origin:
                sale_order = self.env['sale.order'].search([('name', '=', invoice.invoice_origin)], limit=1)
                db_name = self.env.cr.dbname  # ✅ ชื่อ database ปัจจุบัน
                if db_name != "NPD_Logistics_New":

                    if sale_order and sale_order.rental_status != 'returned':
                        rent_days = sale_order.pfb_date_of_rent or 0
                        remaining_days = 0
                        overdue_days = 0

                        if sale_order.rent_days_overdue <= 30:
                            if sale_order.end_rent_date:
                                try:
                                    end_date = fields.Date.from_string(sale_order.end_rent_date)
                                    remaining_days = max((end_date - today).days, 0)
                                    overdue_days = max((today - end_date).days, 0) if today > end_date else 0
                                except Exception as e:
                                    _logger.warning(
                                        f"[⚠️] Error parsing end_rent_date for sale order {sale_order.name}: {e}")

                            sale_order.sudo().write({
                                'rent_days_remaining': f"{rent_days}/{remaining_days}",
                                'rent_days_overdue': overdue_days
                            })

                            # 🔁 ตั้งค่า rental_status ตามเงื่อนไข
                            new_status = 'in_rent'

                            if sale_order.pricelist_id.name == 'เรทวัน':
                                if remaining_days == 1:
                                    new_status = 'nearly_due'

                                if rent_days == remaining_days:
                                    new_status = 'in_rent'


                            elif sale_order.pricelist_id.name == 'เรทเดือน':
                                if remaining_days == 3 and remaining_days != 0:
                                    new_status = 'nearly_due'

                                if rent_days == remaining_days:
                                    new_status = 'in_rent'

                            if remaining_days == 0:
                                new_status = 'due_date'

                            sale_order.sudo().write({'rental_status': new_status})
                            _logger.info(f"🟢 Updated rental_status → {new_status} for Sale Order: {sale_order.name}")


        # if self.payment_method_one_id.name == 'หักเงินประกันค่าเช่า':
        #     for invoice in self.invoice_ids:
        #         print("invoice",invoice.name)
        #         invoice.write({
        #             'payment_id': self.id,
        #             'payment_state': 'paid'
        #         })

    def update_voucher_with_payment(self):
        print("🚀 เริ่ม update_voucher_with_payment")
        for payment in self:
            if not payment.invoice_ids:
                print(f"⚠️ Payment {payment.name or payment.id} ไม่มี invoice_ids")
                continue

            for inv in payment.invoice_ids:
                print("🔍 ตรวจ Invoice:", inv.id, inv.name)
                print("🔍 ตรวจ partner_id.name:", payment.partner_id.name)

                # ค้นหา voucher ที่มี invoice นี้
                vouchers = self.env['account.voucher'].search([
                    ('partner_id', '=', payment.partner_id.id),
                    ('invoice_ids', 'in', [inv.id])
                ])


                for voucher in vouchers:
                    print("xxxxxxxxxxxxxxxxxxxxxxx",voucher.invoice_ids.name)
                    if payment.id not in voucher.payment_t_ids.ids:
                        voucher.payment_t_ids = [(4, payment.id)]
                        print(f"✅ เพิ่ม Payment ID {payment.id} → Voucher ID {voucher.id}")
                    else:
                        print(f"⚠️ Payment ID {payment.id} มีอยู่แล้วใน Voucher ID {voucher.id}")

    def group_account_tax_invoice(self):
        for tax_invoice in self.tax_invoice_ids:
            account_tax = self.env["account.tax"].search([])
            account_repartition = self.env["account.tax.repartition.line"].search([])
            for line in tax_invoice.move_id.line_ids:
                if account_tax.filtered(lambda tax: tax.cash_basis_transition_account_id == line.account_id) \
                    or account_repartition.filtered(lambda tax: tax.account_id == line.account_id):
                    line.with_context(check_move_validity=False).move_id = self.move_id.id
                    line.with_context(check_move_validity=False).name = line.account_id.name
            tax_invoice.move_id.tax_cash_basis_rec_id = None
            tax_invoice.move_id.button_cancel()
            tax_invoice.move_id.with_context(force_delete=True).unlink()
            tax_invoice.move_id = self.move_id

    def cheque_assigned(self):
        if self.is_payment_multi == False \
                and self.type == 'cheque' \
                and self.cheque_id.state == 'draft':
            self.cheque_id.action_assigned()
        else:
            for line in self.paid_ids:
                if line.type == 'cheque' \
                        and line.cheque_id \
                        and line.cheque_id.state == 'draft':
                    line.cheque_id.action_assigned()

    # def _reconcile_payment(self):
    #     for invoice in self.invoice_ids:
    #         if invoice.paid_total > 0:
    #             lines = invoice.invoice_id.line_ids.filtered(
    #                 lambda line: line.account_id.id == self.destination_account_id.id
    #                 and not line.reconciled
    #             )
    #             print("📌 ตรวจสอบ invoice:", invoice.invoice_id.name)
    #             print("🧾 destination_account_id:", self.destination_account_id.code)
    #             print("📑 lines in invoice (ยังไม่ reconcile):", lines.mapped("name"))
    #             lines += self.move_id.line_ids.filtered(
    #                 lambda line: line.account_id.id == self.destination_account_id.id
    #                 and line.account_id.reconcile is True
    #                 and line.invoice_id == invoice.invoice_id
    #             )
    #             print("📦 lines from payment move_id:", lines.mapped("name"))
    #             lines.reconcile()
    def _reconcile_payment(self):
        """Reconcile payment with invoices - รองรับกรณีมีส่วนลด"""
        for invoice in self.invoice_ids:
            if invoice.paid_total > 0:
                invoice_obj = invoice.invoice_id

                # คำนวณส่วนลดของ invoice นี้
                invoice_discount = 0
                if hasattr(invoice_obj, 'amount_discount') and invoice_obj.amount_discount > 0:
                    invoice_discount = invoice_obj.amount_discount
                else:
                    for inv_line in invoice_obj.invoice_line_ids:
                        if hasattr(inv_line, 'discount_amount') and inv_line.discount_amount > 0:
                            invoice_discount += inv_line.discount_amount
                        elif hasattr(inv_line, 'discount') and inv_line.discount > 0:
                            line_discount = (inv_line.price_unit * inv_line.quantity * inv_line.discount / 100)
                            invoice_discount += line_discount

                # หาบัญชีที่ต้อง reconcile
                invoice_accounts = invoice_obj.line_ids.mapped('account_id').filtered(lambda a: a.reconcile)

                for account in invoice_accounts:
                    # หา lines จาก invoice
                    invoice_lines = invoice_obj.line_ids.filtered(
                        lambda line: line.account_id.id == account.id and not line.reconciled
                    )

                    # หา lines จาก payment
                    payment_lines = self.move_id.line_ids.filtered(
                        lambda line: line.account_id.id == account.id and not line.reconciled
                    )

                    if invoice_lines and payment_lines:
                        try:
                            # ถ้ามีส่วนลด ใช้ partial reconciliation
                            if invoice_discount > 0:
                                # Force reconciliation แม้ยอดไม่ตรงกัน
                                (invoice_lines + payment_lines).with_context(
                                    skip_invoice_sync=True,
                                    force_amount=True,
                                    no_exchange_difference=True
                                ).reconcile()

                                _logger.info(f"✅ Partial reconcile (with discount) บัญชี: {account.code}")
                            else:
                                # Standard reconciliation
                                (invoice_lines + payment_lines).reconcile()
                                _logger.info(f"✅ Full reconcile บัญชี: {account.code}")

                        except Exception as e:
                            _logger.warning(f"⚠️ Reconcile error for {account.code}: {str(e)}")

                # อัพเดต payment state ถ้าจ่ายครบแล้ว (รวมส่วนลด)
                if invoice.paid_total + invoice_discount >= invoice.amount_due:
                    # Mark as paid if fully paid including discount
                    if invoice_obj.payment_state != 'paid':
                        invoice_obj.with_context(force_payment_state=True).write({
                            'payment_state': 'paid'
                        })
                        _logger.info(f"✅ Invoice {invoice_obj.name} marked as PAID (with discount)")

    def check_payment_balance(self):
        """ตรวจสอบว่า Journal Entry balance หรือไม่"""
        for payment in self:
            total_debit = sum(payment.move_id.line_ids.mapped('debit'))
            total_credit = sum(payment.move_id.line_ids.mapped('credit'))

            _logger.info(f"""
            Payment Check for {payment.name}:
            - Total Debit: {total_debit}
            - Total Credit: {total_credit}
            - Balance: {total_debit - total_credit}
            - Has Discount: {any(line.name and 'ส่วนลด' in line.name for line in payment.move_id.line_ids)}
            """)

            if abs(total_debit - total_credit) > 0.01:
                _logger.error(f"❌ Journal Entry ไม่ balance!")
                return False
            return True

    @api.onchange('invoice_ids')
    def _onchange_invoice_ids_sync_name(self):
        if self.invoice_ids:
            journal_names = []
            names = []

            for inv in self.invoice_ids:
                if inv.paid and inv.invoice_id:
                    names.append(inv.invoice_id.name)
                    if inv.invoice_id.journal_id:
                        journal_names.append(inv.invoice_id.journal_id.name)

            self.search_invoice_name = ', '.join(names)
            print("📌 Journal Names จากใบแจ้งหนี้ที่ติ๊กเลือก (paid=True):", journal_names)

            if 'สมุดรายวันค่าประกัน' in journal_names:
                journal = self.env['account.journal'].search([
                    ('name', '=', 'สมุดรายวันรับชำระค่าประกัน')
                ], limit=1)
                if journal:
                    print("✅ ตั้งค่า journal เป็น:", journal.name)
                    self.journal_id = journal.id
                else:
                    raise UserError("ไม่พบสมุดรายวัน 'สมุดรายวันรับชำระค่าประกัน'")

            if 'สมุดรายวันค่าปรับชำรุด' in journal_names:
                journal = self.env['account.journal'].search([
                    ('name', '=', 'สมุดรายวันรับชำระค่าปรับชำรุด')
                ], limit=1)
                if journal:
                    self.journal_id = journal.id
                else:
                    raise UserError("ไม่พบสมุดรายวัน 'สมุดรายวันรับชำรุด'")

            if 'สมุดรายวันค่าปรับหาย' in journal_names:
                journal = self.env['account.journal'].search([
                    ('name', '=', 'สมุดรายวันรับชำระค่าปรับหาย')
                ], limit=1)
                if journal:
                    self.journal_id = journal.id
                else:
                    raise UserError("ไม่พบสมุดรายวัน 'สมุดรายวันค่าปรับหาย'")

            if 'สมุดรายวันขาย' in journal_names:
                journal = self.env['account.journal'].search([
                    ('name', '=', 'สมุดรายวันรับชำระ')
                ], limit=1)
                if journal:
                    self.journal_id = journal.id
                else:
                    raise UserError("ไม่พบสมุดรายวัน 'account'")

            if 'สมุดรายวันเช่า(สาขา)' in journal_names:
                journal = self.env['account.journal'].search([
                    ('name', '=', 'สมุดรายวันรับชำระ')
                ], limit=1)
                if journal:
                    self.journal_id = journal.id
                else:
                    raise UserError("ไม่พบสมุดรายวัน 'account'")

    def _onchange_currency_id(self):
        line = self.get_invoice()
        value = {}
        value.update(invoice_ids=line)
        return {"value": value}

    def get_invoice(self):


        line = []
        type_invoice = {'inbound': 'out_invoice', 'outbound': 'in_invoice'}
        self.invoice_ids = None

        domain = [
            ("partner_id", "=", self.partner_id.id),
            ("move_type", "=", type_invoice[self.payment_type]),
            ("state", "=", "posted"),
            ("payment_state", "not in", ["paid", "reversed"]),
            ("currency_id", "=", self.currency_id.id),
        ]

        if self.search_invoice_name:
            domain.append(("name", "ilike", self.search_invoice_name.strip()))

        invoice_list = self.env["account.move"].search(domain)
        for invoice in invoice_list:
            if invoice.amount_residual > 0:
                if self.search_invoice_name:
                    line.append(
                        (
                            0,
                            0,
                            {
                                "invoice_id": invoice.id,
                                "amount_due": invoice.amount_residual or 0.0,
                                "amount_total": invoice.amount_total or 0.0,
                                "wht_total": invoice.wht_amt,
                                "wht_base": invoice.wht_base,
                                # ✅ เพิ่มตรงนี้
                                "paid": True,
                                "paid_total": invoice.amount_residual or 0.0,
                            },
                        )
                    )

                else:
                    line.append(
                        (
                            0,
                            0,
                            {
                                "invoice_id": invoice.id,
                                "amount_due": invoice.amount_residual or 0.0,
                                "amount_total": invoice.amount_total or 0.0,
                                "wht_total": invoice.wht_amt,
                                "wht_base": invoice.wht_base,
                                # "paid": True,
                                # "paid_total": invoice.amount_residual or 0.0,
                            },
                        )
                    )
        return line


    # def get_invoice(self):
    #     line = []
    #     type_invoice = {'inbound': 'out_invoice', 'outbound': 'in_invoice'}
    #     self.invoice_ids = None
    #     domain = [
    #             ("partner_id", "=", self.partner_id.id),
    #             ("move_type", "=", type_invoice[self.payment_type]),
    #             ("state", "=", "posted"),
    #             ("payment_state", "not in", ["paid", "reversed"]),
    #             ("currency_id", "=", self.currency_id.id),
    #         ]
    #     # if self.currency_id != self.company_id.currency_id:
    #     #     domain.append(("currency_id", "=", self.currency_id.id))
    #
    #     invoice_list = self.env["account.move"].search(domain)
    #     for invoice in invoice_list:
    #         if invoice.amount_residual > 0:
    #             line.append(
    #                 (
    #                     0,
    #                     0,
    #                     {
    #                         "invoice_id": invoice.id,
    #                         "amount_due": (invoice.amount_residual or 0.0),
    #                         "amount_total": (invoice.amount_total or 0.0),
    #                         "wht_total": invoice.wht_amt,
    #                         "wht_base": invoice.wht_base,
    #                     },
    #                 )
    #             )
    #     return line

    @api.onchange("partner_id", "search_invoice_name")
    def _onchange_partner_id(self):
        value = {}
        if self.partner_id:
            line = self.get_invoice()
            value.update(invoice_ids=line)
            return {"value": value}

    def action_create_cheque_bank(self):
        return {
            'name': _('Create Cheque Bank'),
            'res_model': 'create.cheque.bank',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.payment',
                'active_ids': self.ids,
                'amount': self.paid_amount - self.amount,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    @api.onchange('is_payment_multi')
    def onchange_method(self):
        if self.is_payment_multi:
            self._onchange_paid_ids()
        else:
            self._onchange_paid_amount()
        # self.amount = self.paid_amount - self.wht_amount

    def action_draft(self):
        ''' posted -> draft '''
        if not self.env.user.account_payment_lock_draft_date:
            raise UserError(_("คุณไม่มีสิทธิ์รีเซ็ตเป็นแบบร่างได้ ต้องเป็นเจ้าหน้าที่การเงินส่วนกลางเท่านั้น "))

        super(AccountPayment, self).action_draft()
        for line in self.move_id.line_ids:
            if line.account_id.user_type_id.name in ('Current Liabilities', 'Current Assets', 'สินทรัพย์หมุนเวียน', 'หนี้สินหมุนเวียน'):
                line.with_context(check_move_validity=False).unlink()

        # if self.r_move_id and self.r_move_id.state == 'posted':
        #     self.r_move_id.button_draft()
        #
        #     # ลบ line หากจำเป็น
        #     self.r_move_id.line_ids.with_context(check_move_validity=False).unlink()
        #
        #     # เปลี่ยน journal ถ้าเกี่ยวข้อง
        #     rental_journal = self.env['account.journal'].search([('name', '=', 'สมุดรายวันเช่า(สาขา)')], limit=1)
        #     if rental_journal:
        #         self.r_move_id.journal_id = rental_journal.id


class AccountPaymentInvoice(models.Model):
    _name = "account.payment.invoice"
    _description = "Account Payment Invoice"

    payment_id = fields.Many2one(
        comodel_name="account.payment",
        string="Payment",
        required=False,
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice Ref",
        required=False,
    )
    name = fields.Char(related="invoice_id.name")
    invoice_date = fields.Date(related="invoice_id.invoice_date")
    threshold_date = fields.Date(related="invoice_id.invoice_date_due")
    origin = fields.Char(related="invoice_id.invoice_origin")
    state = fields.Selection(related="invoice_id.state")
    payment_state = fields.Selection(related="invoice_id.payment_state")
    amount_total = fields.Float(string="Amount Total")
    amount_due = fields.Float(
        string="Residual",
        required=False,
        store=True,
    )
    paid_total = fields.Float(
        string="Paid Total",
        required=False,
    )
    paid_currency_total = fields.Float(
        string="Paid Convert Total",
        store=True,
        compute="_compute_currency_total",
        required=False,
    )
    invoice_currency_total = fields.Float(
        string="Residual Convert Total",
        store=True,
        compute="_compute_invoice_currency_total",
        required=False,
    )
    paid = fields.Boolean(string="Select", default=False)
    wht_total = fields.Float(string='Wht Tax')
    wht_base = fields.Float(string='Wht Base')
    currency_id = fields.Many2one('res.currency', store=True,
        string='Currency',
        related="invoice_id.currency_id")

    def select_paid(self):
        self.paid_total = self.amount_due
        self.paid = True

    def unpaid(self):
        self.paid_total = 0
        self.paid = False

    @api.onchange('paid')
    def onchange_method(self):
        if self.paid is True:
            self.paid_total = self.amount_due
        else:
            self.paid_total = 0

    @api.depends('paid_total')
    def _compute_currency_total(self):
        for rec in self:

            currency_total = rec.payment_id.currency_id._convert(
                    rec.paid_total,
                    rec.invoice_id.company_id.currency_id,
                    rec.invoice_id.company_id,
                    rec.payment_id.date or fields.Date.context_today(self),
                )
            rec.paid_currency_total = currency_total

    @api.depends('amount_due')
    def _compute_invoice_currency_total(self):
        for rec in self:
            invoice_currency_total = rec.invoice_id.currency_id._convert(
                    rec.amount_due,
                    rec.invoice_id.company_id.currency_id,
                    rec.invoice_id.company_id,
                    rec.invoice_id.date or fields.Date.context_today(self),
                )
            rec.invoice_currency_total = invoice_currency_total

class AccountPaidLine(models.Model):
    _name = "account.paid.line"
    _description = "paid line"

    payment_id = fields.Many2one("account.payment", string="Payment", ondelete="cascade")
    payment_method_id = fields.Many2one("payment.method", string="Payment Method", domain="[('is_active','=',True)]",required=True)
    # bank_id = fields.Many2one("res.bank", string="Bank Account")
    bank_account_id = fields.Many2one(
        "res.partner.bank", string="Bank Account"
    )
    account_id = fields.Many2one("account.account", related='payment_method_id.account_id', string="Account")
    cheque_id = fields.Many2one("account.cheque", string="Cheque",domain="[('state', '=', 'draft')]")
    # cheque_name = fields.Char(string='Cheque Number')
    total = fields.Float(string="Total", digits=(36, 2), required=True)
    # date = fields.Date(string='Date Payment')
    ref = fields.Char(string="Ref", required=False, )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
    )
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    type = fields.Selection(
        'Payment method',
        related='payment_method_id.type',
        required=True
    )
    is_write_off = fields.Boolean(string="Write Off")



    def create_cheque(self):
        cheque_type = self.payment_id.payment_type == 'inbound' and 'receipt' or 'payment'
        if self.total > 0 and self.cheque_name != '' and self.bank_id:
            cheque_id = self.env['account.cheque'].create({
                    'name': self.cheque_name,
                    'date_cheque': self.date,
                    'cheque_type': cheque_type,
                    'cheque_total': self.total,
                    'partner_id': self.payment_id.partner_id.id,
                    'bank_id': self.bank_id.id,
                    'bank_account_id': self.bank_account_id.id,
                    'account_bank_id': self.bank_account_id.account_bank_id.id,
                    'payment_method_id': self.payment_method_id.id,
                    'payment_id': self.payment_id.id
            })
            self.cheque_id = cheque_id
        return True


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    invoice_id = fields.Many2one('account.move', string='Invoice Id',ondelete="cascade",)

