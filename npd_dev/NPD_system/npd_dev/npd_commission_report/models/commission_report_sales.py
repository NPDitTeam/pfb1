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


class CommissionReportSales(models.TransientModel):
    _name = 'npd.commission.report.sales'
    _description = 'รายงานค่าคอม Sales'

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

    def action_generate_report(self):
        self.ensure_one()
        # ลบข้อมูลเก่า
        self.env['npd.commission.report.sales.line'].search([]).unlink()
        # คำนวณวันที่เริ่มต้นและสิ้นสุดจากเดือนและปีที่เลือก
        year_int = int(self.year)
        month_int = int(self.month)
        date_from = date(year_int, month_int, 1)
        last_day = monthrange(year_int, month_int)[1]
        date_to = date(year_int, month_int, last_day)
        # ✅ ใช้เมธอดกลาง (ตัวเดียวกับ API) เพื่อให้รายงาน = payroll เสมอ
        report_lines = self._compute_sales_data(date_from, date_to)
        if report_lines:
            self.env['npd.commission.report.sales.line'].create(report_lines)
        return {
            'name': 'รายงานค่าคอม Sales',
            'type': 'ir.actions.act_window',
            'res_model': 'npd.commission.report.sales.line',
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
            # คู่จับคู่ที่ "บรรทัดนี้เป็น debit" → counterpart = ฝั่ง credit (เงินรับ/ใบลดหนี้)
            for pr in line.matched_credit_ids:
                cdate = pr.credit_move_id.date
                if cdate and cdate <= as_of:
                    paid += pr.amount or 0.0
            # เผื่อกรณีบรรทัดนี้ไปอยู่ฝั่ง credit
            for pr in line.matched_debit_ids:
                ddate = pr.debit_move_id.date
                if ddate and ddate <= as_of:
                    paid += pr.amount or 0.0
            open_amt = bal - paid
            if open_amt > 0:
                total_open += open_amt
        return total_open / 1.07

    @api.model
    def _compute_sales_data(self, date_from, date_to):
        """คำนวณข้อมูลค่าคอม Sales ต่อ (เซลล์, สาขา) — ใช้ร่วมกับ API /api/commission/sales
        คืน list ของ dict: date_from/date_to/sales_contact_id/branch_id + ยอดต่าง ๆ + net_rental"""
        # ค้นหาสมุดรายวันที่ชื่อ 'สมุดรายวันเช่า(สาขา)' (ค้นหาครั้งเดียว)
        rental_journal = self.env['account.journal'].search([
            ('name', '=', 'สมุดรายวันเช่า(สาขา)')
        ], limit=1)
        
        if not rental_journal:
            raise models.UserError('ไม่พบสมุดรายวันชื่อ "สมุดรายวันเช่า(สาขา)"')
        
        # ดึงข้อมูลจาก account.move โดยตรง
        # - กรองตามสมุดรายวัน 'สมุดรายวันเช่า(สาขา)'
        # - กรองตามวันที่
        # - กรองเฉพาะ contact_type = 'sale'
        # - กรองเฉพาะที่มี sales_contact
        invoices = self.env['account.move'].search([
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('journal_id', '=', rental_journal.id),
            ('state', '=', 'posted'),
            ('move_type', 'in', ['out_invoice']),
            ('contact_type', '=', 'sale'),
            ('sales_contact_id', '!=', False),
        ])
        
        # Group ตาม sales_contact และ branch
        sales_data = {}
        for invoice in invoices:
            # ดึง sales_contact_id จาก account.move เท่านั้น
            sales_contact_id = False
            if invoice.sales_contact_id:
                sales_contact_id = invoice.sales_contact_id.id
            
            # ดึง branch_id จาก invoice
            branch_id = invoice.branch_id.id if invoice.branch_id else False
            
            # ใช้ key เป็น tuple ของ (sales_contact_id, branch_id)
            key = (sales_contact_id, branch_id)
            
            if key not in sales_data:
                sales_data[key] = {
                    'rental_amount': 0.0,
                    'payment_received': 0.0,
                    'outstanding_debt': 0.0,
                    'shipping_cost': 0.0,  # เพิ่มฟิลด์ค่าขนส่ง
                }
            
            # ดึงยอดเช่า (rental_amount) จาก amount_untaxed ของ invoice
            sales_data[key]['rental_amount'] += invoice.amount_untaxed or 0.0

            # ✅ หนี้ค้างชำระ (outstanding_debt) — ยอดค้าง "ณ วันสิ้นรอบ (date_to)" ตามที่การเงินคิด
            #    ครอบคลุมทุกกรณี: ยังไม่จ่าย → ค้างเต็มใบ / จ่ายบางส่วน → ค้างที่เหลือ / จ่ายครบ(ก่อนสิ้นรอบ) → 0
            #    (ใช้ as-of แทน amount_residual เพราะ residual เป็นยอด ณ ปัจจุบัน)
            sales_data[key]['outstanding_debt'] += self._outstanding_residual_asof(invoice, date_to)

        # ✅ หัก "ใบลดหนี้ขาย" (credit note) ออกจากยอดเช่า
        # - สมุดรายวันลดหนี้ขาย, out_refund, posted, contact_type='sale', มี sales_contact, ตามเดือน
        # - จับคู่เซลล์ด้วย sales_contact_id (= ชื่อเซลล์คนนั้น) แล้วลบ amount_untaxed ออก
        credit_note_journal = self.env['account.journal'].search([
            ('name', '=', 'สมุดรายวันลดหนี้ขาย')
        ], limit=1)
        if credit_note_journal:
            # ✅ กรองด้วย "วันที่ของใบลดหนี้เอง" (invoice_date ของ credit note) ตามที่การเงินใช้
            #    เช่น เซลล์พิชชาภัสร์: 494,825.68 − 1,715.89 (ใบลดหนี้ลงวันที่ในเดือนนี้) = 493,109.79
            credit_notes = self.env['account.move'].search([
                ('invoice_date', '>=', date_from),
                ('invoice_date', '<=', date_to),
                ('journal_id', '=', credit_note_journal.id),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_refund'),
                ('contact_type', '=', 'sale'),
                ('sales_contact_id', '!=', False),
            ])
            for cn in credit_notes:
                # จัดกลุ่มตามเซลล์/สาขาของใบลดหนี้ (ให้ลงตรง bucket เดียวกับยอดเช่าที่บวกไว้)
                sales_contact_id = cn.sales_contact_id.id
                branch_id = cn.branch_id.id if cn.branch_id else False
                key = (sales_contact_id, branch_id)
                if key not in sales_data:
                    sales_data[key] = {
                        'rental_amount': 0.0,
                        'payment_received': 0.0,
                        'outstanding_debt': 0.0,
                        'shipping_cost': 0.0,
                    }
                sales_data[key]['rental_amount'] -= cn.amount_untaxed or 0.0

        # หมายเหตุ: หนี้ค้างชำระ (outstanding_debt) ย้ายไปคิดในลูปใบเช่าด้านบนแล้ว
        #   (อิง amount_residual ของใบเช่าที่ออกในเดือนนั้น — ครอบคลุมใบที่ยังไม่จ่ายเลยด้วย)

        # ดึงยอดรับชำระหนี้ (payment_received) จาก account.payment
        # - กรองตามสมุดรายวัน 'สมุดรายวันรับชำระ'
        # - กรองตามวันที่
        # - เงื่อนไข: date ของ payment ต้องคนละเดือนกับ invoice_date และ date > invoice_date
        payment_journal = self.env['account.journal'].search([
            ('name', '=', 'สมุดรายวันรับชำระ')
        ], limit=1)
        
        if payment_journal:
            payments = self.env['account.payment'].search([
                ('journal_id', '=', payment_journal.id),
                ('state', '=', 'posted'),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])
            
            for payment in payments:
                payment_date = payment.date
                # ดึง sales_contact จาก invoice ที่เชื่อมกับ payment
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
                        
                        if is_different_month and is_date_greater:
                            # ดึง sales_contact_id จาก account.move เท่านั้น
                            sales_contact_id = False
                            if inv.sales_contact_id:
                                sales_contact_id = inv.sales_contact_id.id
                            
                            # ข้ามถ้าไม่มี sales_contact
                            if not sales_contact_id:
                                continue
                            
                            # ดึง branch_id จาก invoice
                            branch_id = inv.branch_id.id if inv.branch_id else False
                            
                            # เช็คว่า invoice เป็น contact_type = 'sale' หรือไม่
                            if hasattr(inv, 'contact_type') and inv.contact_type == 'sale':
                                # ใช้ key เป็น tuple ของ (sales_contact_id, branch_id)
                                key = (sales_contact_id, branch_id)
                                
                                if key not in sales_data:
                                    sales_data[key] = {
                                        'rental_amount': 0.0,
                                        'payment_received': 0.0,
                                        'outstanding_debt': 0.0,
                                        'shipping_cost': 0.0,  # เพิ่มฟิลด์ค่าขนส่ง
                                    }
                                
                                sales_data[key]['payment_received'] += (payment.amount or 0.0) / 1.07
                            break  # นับ payment นี้ครั้งเดียว
        
        # ดึงค่าขนส่งจาก account.voucher
        # - กรองตาม ชื่อ sales_contact_id และ สาขา ใน voucher.line_ids
        # - ดึงค่าจาก price_subtotal ในแต่ละ line
        # - Loop ตาม sales_data ที่มีอยู่แล้ว เพื่อหาค่าขนส่งที่ตรงกับ sales และ branch
        for (sales_contact_id, branch_id), data in sales_data.items():
            if not sales_contact_id:
                continue
            
            # ดึงชื่อ sales contact
            sales_user = self.env['res.users'].browse(sales_contact_id)
            sales_name = sales_user.name or ''
            
            # ดึงชื่อ branch
            branch_name = ''
            if branch_id:
                branch_obj = self.env['res.branch'].browse(branch_id)
                branch_name = branch_obj.name or ''
            
            # ค้นหา voucher
            vouchers = self.env['account.voucher'].search([
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('state', '=', 'posted'),
            ])
            
            if vouchers:
                for voucher in vouchers:
                    # ดึง branch จาก voucher (ถ้ามี)
                    voucher_branch_name = ''
                    if hasattr(voucher, 'branch_id') and voucher.branch_id:
                        voucher_branch_name = voucher.branch_id.name or ''
                    
                    # เช็คสาขาของ voucher ตรงกับ branch ที่ต้องการหรือไม่
                    branch_match = False
                    if not branch_name:
                        # ถ้าไม่มี branch ให้ผ่าน
                        branch_match = True
                    elif voucher_branch_name:
                        # เช็คชื่อสาขาตรงกัน
                        branch_match = (branch_name.strip().lower() == voucher_branch_name.strip().lower())
                    
                    if branch_match and hasattr(voucher, 'line_ids'):
                        for line in voucher.line_ids:
                            # เช็คว่า line มี sales_contact_id หรือไม่
                            if hasattr(line, 'sales_contact_id') and line.sales_contact_id:
                                # ดึงชื่อ sales_contact จาก line
                                line_sales_name = line.sales_contact_id.name or ''
                                
                                # เช็คว่าชื่อ sales ตรงกันหรือไม่ (exact match)
                                if line_sales_name.strip().lower() == sales_name.strip().lower():
                                    # รวมยอดค่าขนส่ง
                                    data['shipping_cost'] += line.price_subtotal or 0.0
        
        # สร้างข้อมูลรายงาน (เฉพาะที่มี sales_contact_id)
        report_lines = []
        for (sales_contact_id, branch_id), data in sales_data.items():
            # ข้ามถ้าไม่มี sales_contact_id
            if not sales_contact_id:
                continue
            
            # คำนวณยอดเช่าสุทธิ (หักค่าขนส่งด้วย)
            net_rental = data['rental_amount'] + data['payment_received'] - data['outstanding_debt'] - data['shipping_cost']
            
            report_lines.append({
                'date_from': date_from,
                'date_to': date_to,
                'sales_contact_id': sales_contact_id,
                'branch_id': branch_id,
                'rental_amount': truncate_decimal(data['rental_amount'], 2),
                'payment_received': truncate_decimal(data['payment_received'], 2),
                'outstanding_debt': truncate_decimal(data['outstanding_debt'], 2),
                'shipping_cost': truncate_decimal(data['shipping_cost'], 2),
                'net_rental': truncate_decimal(net_rental, 2),
            })
        
        return report_lines


class CommissionReportSalesLine(models.TransientModel):
    _name = 'npd.commission.report.sales.line'
    _description = 'รายละเอียดรายงานค่าคอม Sales'
    _order = 'sales_contact_id'

    date_from = fields.Date(string='วันที่เริ่มต้น', readonly=True)
    date_to = fields.Date(string='วันที่สิ้นสุด', readonly=True)
    sales_contact_id = fields.Many2one('res.users', string='Sales ที่ติดต่อ', readonly=True)
    branch_id = fields.Many2one('res.branch', string='สาขา', readonly=True)
    rental_amount = fields.Float(string='ยอดเช่า', readonly=True, digits=(16, 2))
    payment_received = fields.Float(string='รับชำระหนี้', readonly=True, digits=(16, 2))
    outstanding_debt = fields.Float(string='หนี้ค้างชำระ', readonly=True, digits=(16, 2))
    shipping_cost = fields.Float(string='ค่าขนส่ง', readonly=True, digits=(16, 2))
    net_rental = fields.Float(string='ยอดเช่าสุทธิ', readonly=True, digits=(16, 2))
