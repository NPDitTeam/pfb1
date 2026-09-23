# -*- coding: utf-8 -*-
"""ออกใบแจ้งหนี้จากหน้าชำระหนี้บ้านเขียว — แยกใบตาม "ประเภทหนี้"

ลูกค้าชำระเป็นประเภท ไม่ได้ชำระรวมก้อนเดียว ถ้าออกใบเดียว 6 บรรทัด Odoo จะตัด
ชำระที่ระดับ "ใบ" ทำให้ไม่รู้ว่าเงินที่เข้ามาไปตัดประเภทไหน จึงออกใบแยกประเภท
แล้วอ่านสถานะ/ยอดคงเหลือของแต่ละใบกลับมาแสดงบนหน้าลูกหนี้
"""
from odoo import models, fields, api
from odoo.exceptions import UserError

DEBT_TYPE_SELECTION = [
    ('rent', 'ค่าเช่า'),
    ('vat', 'Vat'),
    ('tax', 'Tax'),
    ('lost', 'ค่าปรับหาย'),
    ('broken', 'ค่าปรับชำรุด'),
    ('transport', 'ค่าขนส่ง'),
]
# ประเภทหนี้ -> ชื่อฟิลด์ยอดบนลูกหนี้
DEBT_TYPE_FIELD = {
    'rent': 'amount',
    'vat': 'vat',
    'tax': 'tax',
    'lost': 'lost',
    'broken': 'broken',
    'transport': 'transport',
}
JOURNAL_PARAM = 'baankheaw_debt_payment.journal_code'
ACCOUNT_PARAM = 'baankheaw_debt_payment.income_account_code'


class AccountMove(models.Model):
    _inherit = 'account.move'

    bk_debt_payment_id = fields.Many2one(
        'baankheaw.debt_payment', string='ลูกหนี้บ้านเขียว',
        index=True, ondelete='set null', copy=False,
        help='ใบแจ้งหนี้นี้ออกจากหน้าชำระหนี้บ้านเขียว')
    bk_debt_type = fields.Selection(
        DEBT_TYPE_SELECTION, string='ประเภทหนี้ (บ้านเขียว)', copy=False, index=True,
        help='ออกใบแยกตามประเภท เพื่อให้รู้ว่าเงินที่รับมาตัดหนี้ประเภทไหน')


class BaankheawDebtPaymentInvoice(models.Model):
    _inherit = 'baankheaw.debt_payment'

    partner_id = fields.Many2one('res.partner', string='ผู้ติดต่อสำหรับออกบิล',
                                 help='ใช้เป็นลูกค้าบนใบแจ้งหนี้ ระบบจับคู่จากชื่อให้อัตโนมัติ')
    invoice_ids = fields.One2many('account.move', 'bk_debt_payment_id',
                                  string='ใบแจ้งหนี้')
    invoice_count = fields.Integer(string='จำนวนใบแจ้งหนี้',
                                   compute='_compute_invoice_totals')
    invoiced_total = fields.Float(string='ออกบิลแล้ว', digits=(16, 2),
                                  compute='_compute_invoice_totals')
    invoice_paid_total = fields.Float(string='ชำระแล้ว (จากใบแจ้งหนี้)', digits=(16, 2),
                                      compute='_compute_invoice_totals')
    invoice_residual_total = fields.Float(string='คงเหลือตามใบแจ้งหนี้', digits=(16, 2),
                                          compute='_compute_invoice_totals')

    @api.depends('invoice_ids.amount_total', 'invoice_ids.amount_residual',
                 'invoice_ids.state')
    def _compute_invoice_totals(self):
        for rec in self:
            live = rec.invoice_ids.filtered(lambda m: m.state != 'cancel')
            rec.invoice_count = len(live)
            rec.invoiced_total = sum(live.mapped('amount_total'))
            rec.invoice_residual_total = sum(
                live.filtered(lambda m: m.state == 'posted').mapped('amount_residual'))
            rec.invoice_paid_total = rec.invoiced_total - rec.invoice_residual_total

    # ------------------------------------------------------------------
    # ตัวช่วยหาข้อมูลตั้งต้นสำหรับออกบิล
    # ------------------------------------------------------------------
    def _bk_effective_amount(self, debt_type):
        """ยอดที่จะใช้ออกบิล — ถ้าศาลสั่งปรับช่องนี้ ใช้ยอดศาล ถ้าไม่ ใช้ยอดเดิม"""
        self.ensure_one()
        field_name = DEBT_TYPE_FIELD[debt_type]
        court_value = self['court_%s' % field_name] or 0.0
        state = self['court_%s_state' % field_name]
        return court_value if state else (self[field_name] or 0.0)

    def _bk_find_partner(self):
        """หาผู้ติดต่อจากชื่อลูกค้า ถ้าไม่มีให้สร้างใหม่

        ข้อมูลลูกหนี้มาจากฐานภายนอก ไม่มี id ของ res.partner ติดมาด้วย
        จึงจับคู่ด้วยชื่อ (ชื่อบริษัทก่อน ถ้าไม่มีใช้ชื่อบุคคล)
        """
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        Partner = self.env['res.partner']
        name = (self.cus_cpnname or '').strip() or (self.cus_fullname or '').strip()
        if not name:
            raise UserError('ลูกหนี้รายนี้ไม่มีชื่อ จึงออกใบแจ้งหนี้ไม่ได้')
        partner = Partner.search([('name', '=', name)], limit=1)
        if not partner:
            partner = Partner.create({
                'name': name,
                'phone': self.cus_tel or self.cus_cpntel or False,
                'street': self.cus_cpnadd or self.cus_address or False,
                'customer_rank': 1,
                'comment': 'สร้างจากหน้าชำระหนี้บ้านเขียว (รหัสลูกค้า %s)' % (self.cus_id or '-'),
            })
        self.partner_id = partner.id
        return partner

    @api.model
    def _bk_invoice_journal(self):
        """สมุดรายวันขายที่จะใช้ ตั้งทับได้ด้วยพารามิเตอร์ baankheaw_debt_payment.journal_code"""
        Journal = self.env['account.journal']
        code = (self.env['ir.config_parameter'].sudo()
                .get_param(JOURNAL_PARAM) or '').strip()
        company = self.env.company
        if code:
            journal = Journal.search([('code', '=', code),
                                      ('company_id', '=', company.id)], limit=1)
            if journal:
                return journal
        journal = Journal.search([('type', '=', 'sale'),
                                  ('company_id', '=', company.id)], limit=1)
        if not journal:
            raise UserError('ไม่พบสมุดรายวันขายของบริษัท %s' % company.display_name)
        return journal

    @api.model
    def _bk_income_account(self, journal):
        """บัญชีรายได้สำหรับบรรทัดในใบแจ้งหนี้"""
        code = (self.env['ir.config_parameter'].sudo()
                .get_param(ACCOUNT_PARAM) or '').strip()
        Account = self.env['account.account']
        company = self.env.company
        if code:
            account = Account.search([('code', '=', code),
                                      ('company_id', '=', company.id)], limit=1)
            if account:
                return account
        if journal.default_account_id:
            return journal.default_account_id
        account = Account.search([
            ('company_id', '=', company.id),
            ('user_type_id.internal_group', '=', 'income'),
        ], limit=1)
        if not account:
            raise UserError('ไม่พบบัญชีรายได้ของบริษัท %s '
                            'กรุณาตั้งค่าพารามิเตอร์ %s' % (company.display_name, ACCOUNT_PARAM))
        return account

    # ------------------------------------------------------------------
    # ปุ่ม
    # ------------------------------------------------------------------
    def action_create_invoices(self):
        """สร้างใบแจ้งหนี้แยกตามประเภทหนี้ (ประเภทละ 1 ใบ)

        - ข้ามประเภทที่ยอดเป็น 0
        - ข้ามประเภทที่มีใบแจ้งหนี้อยู่แล้วและยังไม่ถูกยกเลิก (กันออกซ้ำ)
        - ใบที่ได้เป็น "ฉบับร่าง" ให้ตรวจก่อนลงบัญชีเอง
        """
        Move = self.env['account.move']
        created = Move.browse()
        skipped = []
        for rec in self:
            partner = rec._bk_find_partner()
            journal = rec._bk_invoice_journal()
            account = rec._bk_income_account(journal)
            existing = {
                move.bk_debt_type
                for move in rec.invoice_ids.filtered(lambda m: m.state != 'cancel')
            }
            for debt_type, label in DEBT_TYPE_SELECTION:
                amount = rec._bk_effective_amount(debt_type)
                if amount <= 0.005:
                    continue
                if debt_type in existing:
                    skipped.append('%s: %s (มีใบอยู่แล้ว)' % (rec.cus_fullname, label))
                    continue
                move = Move.create({
                    'move_type': 'out_invoice',
                    'partner_id': partner.id,
                    'journal_id': journal.id,
                    'invoice_date': fields.Date.context_today(rec),
                    'bk_debt_payment_id': rec.id,
                    'bk_debt_type': debt_type,
                    'ref': '%s / %s' % (rec.doc_number or '-', label),
                    'narration': 'ออกจากหน้าชำระหนี้บ้านเขียว\n'
                                 'ลูกค้า %s สาขา %s\nเลขใบกำกับเช่า: %s' % (
                                     rec.cus_fullname or '-', rec.branch_name or '-',
                                     rec.bill_numbers or '-'),
                    'invoice_line_ids': [(0, 0, {
                        'name': '%s — %s' % (label, rec.cus_fullname or ''),
                        'quantity': 1.0,
                        'price_unit': amount,
                        'account_id': account.id,
                        'tax_ids': [(5, 0, 0)],
                    })],
                })
                created |= move
        if not created:
            raise UserError('ไม่มีประเภทหนี้ที่ต้องออกใบแจ้งหนี้\n%s'
                            % ('\n'.join(skipped) if skipped else ''))
        return self.action_view_invoices()

    def action_view_invoices(self):
        """เปิดรายการใบแจ้งหนี้ของลูกหนี้รายนี้"""
        self.ensure_one()
        return {
            'name': 'ใบแจ้งหนี้ของ %s' % (self.cus_fullname or ''),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('bk_debt_payment_id', '=', self.id)],
            'context': {'create': False},
        }
