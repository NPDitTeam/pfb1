# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from odoo import fields, models, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError


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
    date = fields.Date("Bill Date", readonly=True,required=True,
        index=True, states={'draft': [('readonly', False)]},
        copy=False, default=fields.Date.context_today)
    account_date = fields.Date("Accounting Date",
        readonly=True, index=True, states={'draft': [('readonly', False)]},
        help="Effective date for accounting entries", copy=False, default=fields.Date.context_today)
    journal_id = fields.Many2one('account.journal', 'Journal',
        required=True, readonly=True, states={'draft': [('readonly', False)]}, default=_default_journal)
    payment_journal_id = fields.Many2one('account.journal', string='Payment Method', readonly=True,
        states={'draft': [('readonly', False)]}, domain="[('type', 'in', ['cash', 'bank'])]", default=_default_payment_journal)
    account_id = fields.Many2one('account.account', 'Account',
        required=False, readonly=True, states={'draft': [('readonly', False)]},
        domain="[('deprecated', '=', False), ('internal_type','=', (voucher_type == 'purchase' and 'payable' or 'receivable'))]")
    line_ids = fields.One2many('account.voucher.line', 'voucher_id', 'Voucher Lines',
        readonly=True, copy=True,
        states={'draft': [('readonly', False)]})
    narration = fields.Text('Notes', readonly=True, tracking=True,states={'draft': [('readonly', False)]})
    currency_id = fields.Many2one('res.currency', compute='_get_journal_currency',
        string='Currency', readonly=True, store=True, default=lambda self: self._get_currency())
    company_id = fields.Many2one('res.company', 'Company',
        store=True, readonly=True,
        default=lambda self: self._get_company())
    state = fields.Selection([
        ('draft', 'Draft'),
           ('paid', 'paid'),
        ('cancel', 'Cancelled'),
        ('proforma', 'Pro-forma'),
        ('posted', 'Posted')
        ], 'Status', readonly=True,  copy=False, default='draft',tracking=True,
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
    partner_id = fields.Many2one('res.partner', 'Partner', required=True, change_default=1, readonly=True, states={'draft': [('readonly', False)]})
    paid = fields.Boolean(compute='_check_paid', help="The Voucher has been totally paid.")
    pay_now = fields.Selection([
            ('pay_now', 'Pay Directly'),
            ('pay_later', 'Pay Later'),
        ], 'Payment', index=True, readonly=True, states={'draft': [('readonly', False)]}, default='pay_now')
    date_due = fields.Date('Due Date', readonly=True, index=True, states={'draft': [('readonly', False)]})
    payment_method_id = fields.Many2one('payment.method', string='Payment Method',required=False,  tracking=True,domain="[('is_active','=',True),'|',('company_id', '=', False),('company_id', '=', company_id)]")
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
    payment_ids = fields.One2many(comodel_name="account.voucher.payment", inverse_name="voucher_id", string="payment", required=False, )
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
    tax_line = fields.One2many(comodel_name="account.move.tax.invoice", inverse_name="voucher_id", string="", required=False, )
    old_move_name = fields.Char(
        string="Old Move name",
        required=False,
    )


    check_show = fields.Boolean(string="Check Show", default=False)  # รับค่าจาก context (default_check_show)
    check_type_show_selection = fields.Selection(
        [('true', 'True'), ('false', 'False')],
        string="Check Type Show",
        compute="_compute_check_type_show",
        store=True
    )

    no_deduction = fields.Boolean(string="ไม่หักค่าประกัน", default=False)

    invoice_ids = fields.Many2many(
        'account.move',
        string='หนี้ค้างชำระ',
        domain=[],  # จะควบคุมผ่าน @api.onchange
    )


    total_outstanding = fields.Float(
        string='ยอดหนี้ค้างชำระรวม',
        store=True,
        digits=(12, 2)
    )

    @api.depends("check_show")
    def _compute_check_type_show(self):
        for record in self:
            record.check_type_show_selection = 'true' if record.check_show else 'false'
            print("record.check_type_show_selection", record.check_type_show_selection)
            print("record.check_show", record.check_show)

    @api.model
    def default_get(self, fields):
        """ดึงค่า `default_check_show` จาก `context` และตั้งค่าให้ `check_show`"""
        res = super(AccountVoucher, self).default_get(fields)
        res['check_show'] = self.env.context.get('default_check_show', False)  # ถ้าไม่มีค่า ให้เป็น False
        return res

    # @api.depends('invoice_ids')
    # def _compute_total_outstanding(self):
    #     for rec in self:
    #         rec.total_outstanding = sum(
    #             self.env['account.move'].browse(rec.invoice_ids.ids).mapped('amount_residual'))


    @api.onchange('partner_id')
    def _compute_check_type(self):

        for rec in self:
            domain = []

            if rec.partner_id:
                domain = [
                    ('partner_id', '=', rec.partner_id.id),
                    ('move_type', '=', 'out_invoice'),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                    ('state', '=', 'posted'),
                ]
            return {
                'domain': {
                    'invoice_ids': domain
                }
            }

    @api.depends('move_id.line_ids.reconciled', 'move_id.line_ids.account_id.internal_type')
    def _check_paid(self):
        self.paid = any([((line.account_id.internal_type, 'in', ('receivable', 'payable')) and line.reconciled) for line in self.move_id.line_ids])


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
                tax_info = line.tax_ids.compute_all(line.price_unit, voucher.currency_id, line.quantity, line.product_id, voucher.partner_id)
                for t in tax_info.get('taxes', False):
                    tax_vals.setdefault(
                        t['id'], {"amount": 0.0, "base": 0.0, "account_id": "", "tax_repartition_line_id":""}
                    )
                    tax_vals[t['id']]["account_id"] = t['account_id']
                    tax_vals[t['id']]["name"] = t['name']
                    tax_vals[t['id']]["tax_repartition_line_id"] = t['tax_repartition_line_id']
                    tax_vals[t['id']]["amount"] += t["amount"]
                    tax_vals[t['id']]["base"] += t["base"]
            return tax_vals

    @api.depends('tax_correction', 'line_ids.price_subtotal','wt_cert_ids')
    def _compute_total(self):
        tax_calculation_rounding_method = self.env.user.company_id.tax_calculation_rounding_method
        for voucher in self:
            total = 0
            tax_amount = 0
            tax_lines_vals_merged = {}

            for line in voucher.line_ids:
                tax_info = line.tax_ids.compute_all(line.price_unit, voucher.currency_id, line.quantity, line.product_id, voucher.partner_id)
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


    def proforma_voucher(self):
        self.action_move_line_create()

    def action_cancel_draft(self):
        self.write({'state': 'draft'})


    def cancel_voucher(self):
        for voucher in self:
            voucher.old_move_name = voucher.move_id.name
            voucher.move_id.button_cancel()
            voucher.move_id.unlink()
            voucher.message_post(body="<p><b>Cancel Receipts </b> </p>"
                                      "<p><b>Cancel Date:</b> %s </p>"
                                      "<p><b>Total:</b> %s </p>" % (datetime.today().strftime('%d/%m/%Y'),voucher.amount))
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
        #set the first line of the voucher

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

    def multi_move_line_get(self, move_id, company_currency, current_currency,payment_method_id, amount):
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
        #set the first line of the voucher
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
            return voucher.currency_id._convert(amount, voucher.company_id.currency_id, voucher.company_id, voucher.account_date)

    def _create_tax_move(self,move_id,move_line_id,tax_line_id,tax_base=0.00,tax_amount=0.00):
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

            #create one move line per voucher line where amount is not 0.0
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
                'tax_ids': [(4,t.id) for t in line.tax_ids],
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
            self._create_tax_move(move_id, move_line_id, tax,tax_vals[tax]['base'],tax_vals[tax]['amount'])
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
                move_line = self.env['account.move.line'].with_context(ctx).create(voucher.with_context(ctx).first_move_line_get(move.id, company_currency, current_currency))
            else:
                for payment in voucher.payment_ids:
                    move_line = self.env['account.move.line'].with_context(ctx).create(voucher.with_context(ctx).multi_move_line_get(move.id, company_currency, current_currency,payment.payment_method_id, payment.total))
            line_total = move_line.debit - move_line.credit
            if voucher.voucher_type == 'sale':
                line_total = line_total - voucher._convert(voucher.tax_amount)
            elif voucher.voucher_type == 'purchase':
                line_total = line_total + voucher._convert(voucher.tax_amount)

            #MEMO Create move line with wht certificate
            for wht_line in self.wt_cert_ids:
                move_line = self.env['account.move.line'].with_context(ctx).create(
                    voucher.with_context(ctx).wht_move_line_get(move.id, company_currency, current_currency, wht_line))

            # Create one move line per voucher line where amount is not 0.0
            line_total = voucher.with_context(ctx).voucher_move_line_create(line_total, move.id, company_currency, current_currency)
            #Create move line vat
            voucher.with_context(ctx).vat_move_line_create(move.id,company_currency,current_currency)


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
                tax_move_line = self.env['account.move.line'].search([('move_id', '=', move.id), ('tax_line_id', '!=', False)], limit=1)
                if len(tax_move_line):
                    tax_move_line.write({'debit': tax_move_line.debit + voucher.tax_correction if tax_move_line.debit > 0 else 0,
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
    price_unit = fields.Float(string='Unit Price', required=True, digits=dp.get_precision('Product Price'), oldname='amount')
    price_subtotal = fields.Monetary(string='Amount',
        store=True, readonly=True, compute='_compute_subtotal')
    quantity = fields.Float(digits=dp.get_precision('Product Unit of Measure'),
        required=True, default=1)
    account_analytic_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    company_id = fields.Many2one('res.company', related='voucher_id.company_id', string='Company', store=True, readonly=True)
    tax_ids = fields.Many2many('account.tax', string='Tax', help="Only for tax excluded from price")
    currency_id = fields.Many2one('res.currency', related='voucher_id.currency_id', readonly=False)
    wht_total = fields.Float(string="Withholding Tax",  required=False, digits=dp.get_precision('Product Price'))

    can_edit_voucher = fields.Boolean(
        string="Can Edit Voucher",
        compute="_compute_can_edit_voucher",
        store=False
    )

    @api.depends('price_unit', 'tax_ids', 'quantity', 'product_id', 'voucher_id.currency_id')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
            if line.tax_ids:
                taxes = line.tax_ids.compute_all(line.price_unit, line.voucher_id.currency_id, line.quantity, product=line.product_id, partner=line.voucher_id.partner_id)
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


    def product_id_change(self, product_id, partner_id=False, price_unit=False, company_id=None, currency_id=None, type=None):
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
    company_id = fields.Many2one('res.company', related='voucher_id.company_id', string='Company', store=True, readonly=True)

    payment_method_id = fields.Many2one("payment.method", string="Payment Method",
                                        required=True)
    bank_account_id = fields.Many2one(
        "res.partner.bank", string="Bank Account"
    )
    account_id = fields.Many2one("account.account", related='payment_method_id.account_id', string="Account")
    cheque_id = fields.Many2one("account.cheque", string="Cheque",domain="[('state', '=', 'draft')]")
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
            voucher_id = cheque.voucher_id.search([('cheque_id','=', cheque.id)], limit=1)
            voucher_line_ids = self.env['account.voucher.payment'].search([('cheque_id','=', cheque.id)])
            for voucher_line in voucher_line_ids:
                voucher_id = voucher_line.voucher_id
            cheque.voucher_id = voucher_id

class AccountMove(models.Model):
    _inherit = "account.move"

    voucher_id = fields.Many2one('account.voucher', string='Account Voucher', ondelete="cascade", readonly=True)