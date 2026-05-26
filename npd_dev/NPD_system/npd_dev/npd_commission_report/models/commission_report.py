# -*- coding: utf-8 -*-
from odoo import models, fields, api
from calendar import monthrange
from datetime import date
import json
import math


def truncate_decimal(value, decimals=2):
    """ตัดทศนิยมโดยไม่ปัดเศษ เช่น 1234.567 -> 1234.56"""
    multiplier = 10 ** decimals
    return math.trunc(value * multiplier) / multiplier


class CommissionReport(models.TransientModel):
    _name = 'npd.commission.report'
    _description = 'รายงานค่าคอมมิชชั่น'

    @api.model
    def _get_year_selection(self):
        current_year = fields.Date.today().year
        years = []
        for y in range(current_year - 5, current_year + 2):
            years.append((str(y), str(y)))
        return years

    month = fields.Selection(
        selection=[
            ('1', 'มกราคม'),
            ('2', 'กุมภาพันธ์'),
            ('3', 'มีนาคม'),
            ('4', 'เมษายน'),
            ('5', 'พฤษภาคม'),
            ('6', 'มิถุนายน'),
            ('7', 'กรกฎาคม'),
            ('8', 'สิงหาคม'),
            ('9', 'กันยายน'),
            ('10', 'ตุลาคม'),
            ('11', 'พฤศจิกายน'),
            ('12', 'ธันวาคม'),
        ],
        string='เดือน',
        required=True,
        default=lambda self: str(fields.Date.today().month)
    )
    year = fields.Selection(
        selection='_get_year_selection',
        string='ปี',
        required=True,
        default=lambda self: str(fields.Date.today().year)
    )
    branch_id = fields.Many2one(
        'res.branch',
        string='สาขา',
        help='เว้นว่างเพื่อแสดงทุกสาขา'
    )

    def action_generate_report(self):
        self.ensure_one()
        # ลบข้อมูลเก่า
        self.env['npd.commission.report.line'].search([]).unlink()
        # ดึงรายการสาขา
        if self.branch_id:
            branches = self.branch_id
        else:
            branches = self.env['res.branch'].search([])
        # คำนวณวันที่เริ่มต้นและสิ้นสุดจากเดือนและปีที่เลือก
        year_int = int(self.year)
        month_int = int(self.month)
        date_from = date(year_int, month_int, 1)
        last_day = monthrange(year_int, month_int)[1]
        date_to = date(year_int, month_int, last_day)
        # ✅ ใช้เมธอดกลาง (ตัวเดียวกับ API) เพื่อให้รายงาน = payroll เสมอ
        report_lines = self._compute_branch_data(date_from, date_to, branches)
        if report_lines:
            self.env['npd.commission.report.line'].create(report_lines)
        return {
            'name': 'รายงานค่าคอมมิชชั่น',
            'type': 'ir.actions.act_window',
            'res_model': 'npd.commission.report.line',
            'view_mode': 'tree',
            'target': 'current',
        }

    @api.model
    def _outstanding_residual_asof(self, invoice, as_of):
        """ยอดค้างชำระของใบแจ้งหนี้ "ณ วันที่ as_of" (ไม่รวม VAT แล้ว — หารด้วย 1.07)
        - amount_residual ปกติเป็นยอด ณ ปัจจุบัน → ถ้าลูกค้าจ่ายทีหลังยอดจะหด
        - การเงินคิดหนี้ค้าง ณ "วันสิ้นรอบ" จึงต้องคำนวณย้อน: เอายอดลูกหนี้ตั้งต้น
          ลบเฉพาะเงิน/ใบลดหนี้ที่ reconcile เข้ามาโดยคู่จับคู่ลงวันที่ <= as_of
        """
        total_open = 0.0
        recv_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.internal_type == 'receivable')
        for line in recv_lines:
            bal = (line.debit or 0.0) - (line.credit or 0.0)   # ใบขาย/เช่า → ลูกหนี้ฝั่ง debit (>0)
            paid = 0.0
            for pr in line.matched_credit_ids:
                cdate = pr.credit_move_id.date
                if cdate and cdate <= as_of:
                    paid += pr.amount or 0.0
            for pr in line.matched_debit_ids:
                ddate = pr.debit_move_id.date
                if ddate and ddate <= as_of:
                    paid += pr.amount or 0.0
            open_amt = bal - paid
            if open_amt > 0:
                total_open += open_amt
        return total_open / 1.07

    @api.model
    def _compute_branch_data(self, date_from, date_to, branches=None):
        """คำนวณข้อมูลค่าคอมสาขา ต่อสาขา — ใช้ร่วมกับ API /api/commission/branch
        branches=None → ทุกสาขา. คืน list ของ dict (date_from/date_to/branch_id + ยอด + net_rental)"""
        if branches is None:
            branches = self.env['res.branch'].search([])
        # ค้นหาสมุดรายวัน 3 ชื่อ (ค้นหาครั้งเดียว)
        rental_journal_names = [
            'สมุดรายวันเช่า(สาขา)',
            'สมุดรายวันค่าปรับหาย',
            'สมุดรายวันค่าปรับชำรุด',
        ]
        rental_journals = self.env['account.journal'].search([
            ('name', 'in', rental_journal_names)
        ])

        if not rental_journals:
            raise models.UserError('ไม่พบสมุดรายวัน: %s' % ', '.join(rental_journal_names))

        # ✅ "ยอดเช่า" นับเฉพาะสมุดเช่า(สาขา) — ไม่รวมค่าปรับหาย/ชำรุด (ตามที่การเงินคิด)
        #    แต่ "หนี้ค้างชำระ" ยังรวมทุกสมุด (ค่าปรับที่ยังไม่จ่าย ณ สิ้นรอบ ก็เป็นหนี้ค้าง)
        rent_only_journal = rental_journals.filtered(lambda j: j.name == 'สมุดรายวันเช่า(สาขา)')
        rent_only_journal_id = rent_only_journal.id if rent_only_journal else False

        # สร้างข้อมูลรายงาน (รวมยอดตามสาขา)
        report_lines = []
        for branch in branches:
            # ตัวแปรรวมยอดตามสาขา
            total_rental_amount = 0.0
            total_payment_received = 0.0
            total_outstanding_debt = 0.0

            # ดึงข้อมูลจาก account.move โดยตรง
            # - กรองตามสมุดรายวัน: เช่า(สาขา), ค่าปรับหาย, ค่าปรับชำรุด
            # - กรองตามสาขา
            # - กรองตามวันที่
            # - กรองเฉพาะ contact_type = 'branch'
            invoices = self.env['account.move'].search([
                ('invoice_date', '>=', date_from),
                ('invoice_date', '<=', date_to),
                ('journal_id', 'in', rental_journals.ids),
                ('branch_id', '=', branch.id),
                ('state', '=', 'posted'),
                ('move_type', 'in', ['out_invoice']),
                ('contact_type', '=', 'branch'),
            ])

            for invoice in invoices:
                # ดึงยอดเช่า (rental_amount) — เฉพาะสมุดเช่า(สาขา) ไม่รวมค่าปรับหาย/ชำรุด
                if invoice.journal_id.id == rent_only_journal_id:
                    total_rental_amount += invoice.amount_untaxed or 0.0

                # ✅ หนี้ค้างชำระ (outstanding_debt) — ยอดค้าง "ณ วันสิ้นรอบ (date_to)" ตามที่การเงินคิด
                #    ครอบคลุมทุกกรณี: ยังไม่จ่าย → ค้างเต็มใบ / จ่ายบางส่วน → ค้างที่เหลือ / จ่ายครบ(ก่อนสิ้นรอบ) → 0
                #    (ใช้ as-of แทน amount_residual เพราะ residual เป็นยอด ณ ปัจจุบัน)
                total_outstanding_debt += self._outstanding_residual_asof(invoice, date_to)

            # ✅ หนี้ค้างจาก "ใบค่าปรับ" (สินค้าหาย/สินค้าชำรุด) ที่ติด reason_code แต่อยู่ "นอก" 3 สมุดข้างบน
            #    contact_type='branch' = เป็นของสาขา (จึง group ด้วย branch_id) — กันซ้ำด้วย journal NOT IN
            penalty_reasons = self.env['scrap.reason.code'].search([
                ('name', 'in', ['สินค้าหาย', 'สินค้าชำรุด'])
            ])
            if penalty_reasons:
                penalty_invoices = self.env['account.move'].search([
                    ('invoice_date', '>=', date_from),
                    ('invoice_date', '<=', date_to),
                    ('branch_id', '=', branch.id),
                    ('state', '=', 'posted'),
                    ('move_type', '=', 'out_invoice'),
                    ('contact_type', '=', 'branch'),
                    ('reason_code_id', 'in', penalty_reasons.ids),
                    ('journal_id', 'not in', rental_journals.ids),   # กันซ้ำกับลูปข้างบน
                ])
                for pinv in penalty_invoices:
                    total_outstanding_debt += self._outstanding_residual_asof(pinv, date_to)

            # === DEBUG: ใบแจ้งหนี้ (Invoice) ===
            # if 'พัทยา' in (branch.name or ''):
            #     print(f"=== [ใบแจ้งหนี้] สาขา: {branch.name} ===")
            #     print(f"  จำนวนรายการ: {len(invoices)} รายการ")
            #     print(f"  ยอดรวม total_rental_amount (หลังรวมใบแจ้งหนี้): {total_rental_amount:.2f}")
            #     for inv in invoices:
            #         print(f"    - {inv.name} | invoice_date: {inv.invoice_date} | amount_untaxed: {inv.amount_untaxed:.2f}")

            # ดึงใบลดหนี้ (Credit Note) หักออกจากยอดเช่า — เงื่อนไขเดียวกับฝั่ง Sale
            # ✅ กรองด้วย "วันที่ใบลดหนี้เอง" (invoice_date ของ credit note) ตามที่การเงินใช้
            rental_cn_journal = self.env['account.journal'].search([
                ('name', '=', 'สมุดรายวันลดหนี้ขาย')
            ], limit=1)

            if rental_cn_journal:
                rental_credit_notes = self.env['account.move'].search([
                    ('invoice_date', '>=', date_from),
                    ('invoice_date', '<=', date_to),
                    ('journal_id', '=', rental_cn_journal.id),
                    ('branch_id', '=', branch.id),
                    ('state', '=', 'posted'),
                    ('move_type', '=', 'out_refund'),
                    ('contact_type', '=', 'branch'),
                ])

                for cn in rental_credit_notes:
                    total_rental_amount -= cn.amount_untaxed or 0.0

                # === DEBUG: ใบลดหนี้ ===
                # if 'พัทยา' in (branch.name or ''):
                #     is_jan = (month_int == 1 and year_int == current_year)
                #     print(f"=== [ใบลดหนี้] สาขา: {branch.name} | เดือน {month_int}/{year_int} | กรอง payment_state: {'ไม่กรอง' if is_jan else 'paid'} ===")
                #     print(f"  จำนวนรายการ: {len(rental_credit_notes)} รายการ")
                #     print(f"  ยอดรวม total_rental_amount (หลังหักใบลดหนี้): {total_rental_amount:.2f}")
                #     for cn in rental_credit_notes:
                #         print(f"    - {cn.name} | invoice_date: {cn.invoice_date} | amount_untaxed: {cn.amount_untaxed:.2f} | payment_state: {cn.payment_state}")
                #
                #     # === DEBUG: เช็ค CN ทั้งหมดของสาขานี้ (ไม่กรอง contact_type) ===
                #     all_cn = self.env['account.move'].search([
                #         ('invoice_date', '>=', date_from),
                #         ('invoice_date', '<=', date_to),
                #         ('journal_id', '=', rental_cn_journal.id),
                #         ('branch_id', '=', branch.id),
                #         ('state', '=', 'posted'),
                #         ('move_type', 'in', ['out_refund']),
                #     ])
                #     missing_cn = all_cn - rental_credit_notes
                #     print(f"  --- CN ทั้งหมด (ไม่กรอง contact_type): {len(all_cn)} รายการ | ขาดหายไป: {len(missing_cn)} รายการ ---")
                #     for cn in missing_cn:
                #         print(f"    [ขาด] {cn.name} | invoice_date: {cn.invoice_date} | amount_untaxed: {cn.amount_untaxed:.2f} | contact_type: {cn.contact_type} | payment_state: {cn.payment_state}")

            # หมายเหตุ: หนี้ค้างชำระ (outstanding_debt) ย้ายไปคิดในลูปใบเช่าด้านบนแล้ว
            #   (อิง amount_residual ของใบเช่าที่ออกในเดือนนั้น — ครอบคลุมใบที่ยังไม่จ่ายเลยด้วย)

            # ดึงยอดรับชำระหนี้ (payment_received) จาก account.payment
            # - กรองตามสมุดรายวัน: รับชำระ, รับชำระค่าปรับหาย, รับชำระค่าปรับชำรุด
            # - กรองตามวันที่
            # - กรองตาม branch_id
            # - เงื่อนไข: date ของ payment ต้องคนละเดือนกับ invoice_date และ date > invoice_date
            payment_journal_names = [
                'สมุดรายวันรับชำระ',
                'สมุดรายวันรับชำระค่าปรับหาย',
                'สมุดรายวันรับชำระค่าปรับชำรุด',
            ]
            payment_journals = self.env['account.journal'].search([
                ('name', 'in', payment_journal_names)
            ])

            if payment_journals:
                payments = self.env['account.payment'].search([
                    ('journal_id', 'in', payment_journals.ids),
                    ('state', '=', 'posted'),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                    ('branch_id', '=', branch.id),
                ])

                for payment in payments:
                    payment_date = payment.date
                    # ดึง invoice ที่เชื่อมกับ payment ผ่าน reconciled_invoice_ids
                    for inv in payment.reconciled_invoice_ids:
                        # ❌ ใบขาย (เลขขึ้นต้น 'IV' — ไม่ใช่ใบเช่า 'INV') → ไม่นับเป็นรับชำระหนี้
                        if (inv.name or '').strip().upper().startswith('IV'):
                            continue
                        if inv.invoice_date and payment_date:
                            # คนละเดือน: เดือนหรือปีต่างกัน
                            is_different_month = (
                                    inv.invoice_date.month != payment_date.month or
                                    inv.invoice_date.year != payment_date.year
                            )
                            # date ของ payment ต้องมากกว่า invoice_date
                            is_date_greater = payment_date > inv.invoice_date

                            # เช็คว่า invoice เป็น contact_type = 'branch' หรือไม่
                            if is_different_month and is_date_greater:
                                if hasattr(inv, 'contact_type') and inv.contact_type == 'branch':
                                    # ถอด VAT 7% จากยอดรับชำระ
                                    payment_amount = payment.amount or 0.0
                                    total_payment_received += payment_amount / 1.07
                                break  # นับ payment นี้ครั้งเดียว

            # ดึงรายจ่ายรวม (total_expense) จาก Vendor Bills
            total_expense = 0.0

            # ===== ดึงจาก Vendor Bills =====
            vendor_bills = self.env['account.move'].search([
                ('invoice_date', '>=', date_from),
                ('invoice_date', '<=', date_to),
                ('state', '=', 'posted'),
                ('move_type', 'in', ['in_invoice', 'in_refund']),
                ('branch_id', '=', branch.id),
            ])

            # print(f"=== สาขา: {branch.name} ===")
            # print(f"จำนวน vendor_bills: {len(vendor_bills)}")
            if vendor_bills:
                for bill in vendor_bills:
                    # print(f"  Bill: {bill.name}, amount_total: {bill.amount_total}, payment_state: {bill.payment_state}")
                    # print(f"  invoice_payments_widget: {bill.invoice_payments_widget}")
                    # ใช้ invoice_payments_widget เพื่อดึง payment ที่เชื่อมกับ bill
                    if bill.invoice_payments_widget:
                        try:
                            payments_data = json.loads(bill.invoice_payments_widget)
                            # print(f"  payments_data: {payments_data}")
                            if payments_data and 'content' in payments_data:
                                for payment_info in payments_data['content']:
                                    total_expense += payment_info.get('amount', 0.0)
                        except (json.JSONDecodeError, TypeError):
                            pass
            # print(f"total_expense: {total_expense}")
            # ดึงจาก account.advance.clear
            # - กรองจาก account_analytic_id.name ของแต่ละ line
            # - ดึงค่าจาก Amount (price_subtotal) ในรายการ
            advance_clears = self.env['account.advance.clear'].search([
                ('doc_date', '>=', date_from),
                ('doc_date', '<=', date_to),
                ('state', '=', 'post'),
            ])

            if advance_clears:
                for adv_clear in advance_clears:
                    for line in adv_clear.clear_ids:
                        if line.account_analytic_id and line.account_analytic_id.branch_id:
                            # เช็คจาก branch_id ใน account.analytic.account
                            if line.account_analytic_id.branch_id.id == branch.id:
                                # เช็ค tax_ids เพื่อดึงยอดที่ถูกต้อง
                                line_amount = 0.0
                                if line.tax_ids:
                                    tax_names = [tax.name for tax in line.tax_ids]
                                    tax_name_str = ', '.join(tax_names)
                                    if 'ภาษีซื้อรวม Vat 7%' in tax_name_str:
                                        line_amount = line.price_unit or 0.0
                                    elif 'ภาษีซื้อไม่รวม Vat 7%' in tax_name_str:
                                        line_amount = (line.price_unit or 0.0) * 1.07
                                    else:
                                        line_amount = 0.0
                                else:
                                    line_amount = line.price_subtotal or 0.0

                                total_expense += line_amount

            # # print(f"total_expense หลัง advance_clear: {total_expense}")
            # # ดึงจาก account.voucher
            # # - กรองจาก account.voucher.line.account_analytic_id.name แบบ LIKE กับชื่อสาขา
            # # - ดึงค่าจาก price_subtotal ในแต่ละ line
            # vouchers = self.env['account.voucher'].search([
            #     ('date', '>=', date_from),
            #     ('date', '<=', date_to),
            #     ('state', '=', 'posted'),
            # ])
            #
            # if vouchers:
            #     for voucher in vouchers:
            #         # ดึงรายการ line ที่มี Analytic Account เชื่อมกับสาขา
            #         if hasattr(voucher, 'line_ids'):
            #             for line in voucher.line_ids:
            #                 if hasattr(line, 'account_analytic_id') and line.account_analytic_id:
            #                     # เช็คจาก branch_id ใน account.analytic.account
            #                     if line.account_analytic_id.branch_id and line.account_analytic_id.branch_id.id == branch.id:
            #                         total_expense += line.price_subtotal or 0.0


            # ดึงจาก account.voucher.line โดยตรง
            # - กรองจาก payment_date ในแต่ละบรรทัดแทนวันที่หัวเอกสาร
            # - กรองเฉพาะเอกสารที่ state = 'posted'
            # - กรองตาม branch_id ของ account_analytic_id
            voucher_lines = self.env['account.voucher.line'].search([
                ('payment_date', '>=', date_from),
                ('payment_date', '<=', date_to),
                ('voucher_id.state', '=', 'posted'),
                ('account_analytic_id.branch_id', '=', branch.id)
            ])

            for line in voucher_lines:
                total_expense += line.price_subtotal or 0.0

            # คำนวณยอดเช่าสุทธิ (net_rental)
            net_rental = total_rental_amount + total_payment_received - total_outstanding_debt - total_expense

            report_lines.append({
                'date_from': date_from,
                'date_to': date_to,
                'branch_id': branch.id,
                'rental_amount': truncate_decimal(total_rental_amount, 2),
                'payment_received': truncate_decimal(total_payment_received, 2),
                'outstanding_debt': truncate_decimal(total_outstanding_debt, 2),
                'total_expense': truncate_decimal(total_expense, 2),
                'net_rental': truncate_decimal(net_rental, 2),
            })

        # ถ้าไม่มี order ให้สร้างบรรทัดว่างสำหรับแต่ละสาขา
        if not report_lines:
            for branch in branches:
                report_lines.append({
                    'date_from': date_from,
                    'date_to': date_to,
                    'branch_id': branch.id,
                    'rental_amount': 0.0,
                    'payment_received': 0.0,
                    'outstanding_debt': 0.0,
                    'total_expense': 0.0,
                    'net_rental': 0.0,
                })

        return report_lines


class CommissionReportLine(models.TransientModel):
    _name = 'npd.commission.report.line'
    _description = 'รายละเอียดรายงานค่าคอมมิชชั่น'
    _order = 'branch_id'

    date_from = fields.Date(string='วันที่เริ่มต้น', readonly=True)
    date_to = fields.Date(string='วันที่สิ้นสุด', readonly=True)
    branch_id = fields.Many2one('res.branch', string='สาขา', readonly=True)
    rental_amount = fields.Float(string='ยอดเช่า', readonly=True, digits=(16, 2))
    payment_received = fields.Float(string='รับชำระหนี้', readonly=True, digits=(16, 2))
    outstanding_debt = fields.Float(string='หนี้ค้างชำระ', readonly=True, digits=(16, 2))
    total_expense = fields.Float(string='รายจ่ายรวม', readonly=True, digits=(16, 2))
    net_rental = fields.Float(string='ยอดเช่าสุทธิ', readonly=True, digits=(16, 2))
