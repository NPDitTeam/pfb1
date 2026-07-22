# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date, timedelta
import logging

try:
    from bahttext import bahttext
except ImportError:
    bahttext = None

_logger = logging.getLogger(__name__)

# เริ่มดึงข้อมูลหนี้ตั้งแต่ปี 2026 เป็นต้นไป (ข้อมูลปีต่ำกว่า 2026 จะไม่ถูกดึง/ถูกล้างออก)
DEBT_START_DATE = date(2026, 1, 1)
DEBT_START_STR = '2026-01-01'


class NpdDebtSummary(models.Model):
    _name = 'npd.debt.summary'
    _description = 'รวมหนี้ลูกค้า'
    _order = 'partner_name asc'
    _rec_name = 'display_name'

    name = fields.Char(string='เลขที่เอกสาร', default='New', readonly=True, copy=False, index=True,
        help='เลขที่เอกสารสรุปหนี้รวมของลูกค้า')
    display_name = fields.Char(string='ชื่อ', compute='_compute_display_name', store=True)

    @api.depends('name', 'partner_name')
    def _compute_display_name(self):
        for rec in self:
            if rec.partner_name and rec.name and rec.name != 'New':
                rec.display_name = '%s - %s' % (rec.name, rec.partner_name)
            else:
                rec.display_name = rec.name or rec.partner_name or 'New'

    # เก็บไว้เพื่อความเข้ากันได้กับรายงาน (ไม่แสดงในฟอร์ม)
    note = fields.Text(string='หมายเหตุ')

    customer_id = fields.Many2one('res.partner', string='ลูกค้า', required=True, ondelete='cascade',
        index=True, help='ลูกค้า (Commercial Partner)')
    partner_name = fields.Char(string='ชื่อลูกค้า', store=True)
    partner_phone = fields.Char(string='เบอร์โทรศัพท์')
    partner_mobile = fields.Char(string='มือถือ')
    partner_email = fields.Char(string='อีเมล')
    partner_vat = fields.Char(string='เลขที่ผู้เสียภาษี')
    partner_street = fields.Char(string='ที่อยู่')
    partner_street2 = fields.Char(string='ที่อยู่ 2')
    partner_city = fields.Char(string='เมือง')
    partner_state_id = fields.Many2one('res.country.state', string='จังหวัด')
    partner_zip = fields.Char(string='รหัสไปรษณีย์')

    company_id = fields.Many2one('res.company', string='บริษัท',
        default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one('res.currency', string='สกุลเงิน',
        default=lambda self: self.env.company.currency_id)

    last_update = fields.Datetime(string='อัพเดทล่าสุด', readonly=True)

    _sql_constraints = [
        ('customer_uniq', 'unique(customer_id)', 'ลูกค้าแต่ละรายต้องมีได้เพียงรายการเดียว'),
    ]

    # ===== ใบแจ้งหนี้ค้างชำระ =====
    customer_invoice_line_ids = fields.One2many('npd.debt.summary.invoice.line',
        'summary_id', string='ใบแจ้งหนี้ค้างชำระทั้งหมด')
    customer_amount_residual = fields.Monetary(string='ยอดค้างชำระใบแจ้งหนี้',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    # ===== ค่าปรับหาย =====
    customer_penalty_line_ids = fields.One2many('npd.debt.summary.penalty.line',
        'summary_id', string='ค่าปรับหายทั้งหมด')
    customer_penalty_residual = fields.Monetary(string='ค้างชำระค่าปรับหาย',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    # ===== ค่าปรับชำรุด =====
    customer_damage_line_ids = fields.One2many('npd.debt.summary.damage.line',
        'summary_id', string='ค่าปรับชำรุดทั้งหมด')
    customer_damage_residual = fields.Monetary(string='ค้างชำระค่าปรับชำรุด',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    # ===== ค่า Tax (ภาษีหัก ณ ที่จ่าย) =====
    customer_tax_line_ids = fields.One2many('npd.debt.summary.tax.line',
        'summary_id', string='ค่า Tax ทั้งหมด')
    customer_tax_residual = fields.Monetary(string='ค้างชำระค่า Tax',
        currency_field='currency_id', compute='_compute_residuals', store=True)

    @api.depends('customer_invoice_line_ids.amount_residual', 'customer_invoice_line_ids.payment_status',
                 'customer_penalty_line_ids.amount_residual', 'customer_penalty_line_ids.payment_status',
                 'customer_damage_line_ids.amount_residual', 'customer_damage_line_ids.payment_status',
                 'customer_tax_line_ids.tax_amount', 'customer_tax_line_ids.payment_status')
    def _compute_residuals(self):
        for rec in self:
            rec.customer_amount_residual = sum(
                l.amount_residual for l in rec.customer_invoice_line_ids if l.payment_status == 'unpaid')
            rec.customer_penalty_residual = sum(
                l.amount_residual for l in rec.customer_penalty_line_ids if l.payment_status == 'unpaid')
            rec.customer_damage_residual = sum(
                l.amount_residual for l in rec.customer_damage_line_ids if l.payment_status == 'unpaid')
            rec.customer_tax_residual = sum(
                l.tax_amount for l in rec.customer_tax_line_ids if l.payment_status == 'unpaid')

    grand_total = fields.Monetary(string='รวมหนี้ทั้งสิ้น', currency_field='currency_id',
        compute='_compute_grand_total', store=True)

    payment_status = fields.Selection([
        ('unpaid', 'ค้างชำระ'),
        ('paid', 'ชำระแล้ว'),
    ], string='สถานะรวม', compute='_compute_payment_status', store=True, default='unpaid')

    # สถานะแยกตามแต่ละแท็บ
    invoice_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะใบแจ้งหนี้', compute='_compute_payment_status', store=True)
    lost_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะค่าปรับหาย', compute='_compute_payment_status', store=True)
    damage_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะค่าปรับชำรุด', compute='_compute_payment_status', store=True)
    tax_payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'ชำระแล้ว')],
        string='สถานะค่า Tax', compute='_compute_payment_status', store=True)

    @api.depends('customer_invoice_line_ids.payment_status',
                 'customer_penalty_line_ids.payment_status',
                 'customer_damage_line_ids.payment_status',
                 'customer_tax_line_ids.payment_status')
    def _compute_payment_status(self):
        for rec in self:
            inv_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_invoice_line_ids)
            pen_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_penalty_line_ids)
            dmg_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_damage_line_ids)
            tax_unpaid = any(l.payment_status == 'unpaid' for l in rec.customer_tax_line_ids)
            rec.invoice_payment_status = 'unpaid' if inv_unpaid else 'paid'
            rec.lost_payment_status = 'unpaid' if pen_unpaid else 'paid'
            rec.damage_payment_status = 'unpaid' if dmg_unpaid else 'paid'
            rec.tax_payment_status = 'unpaid' if tax_unpaid else 'paid'
            rec.payment_status = 'unpaid' if (inv_unpaid or pen_unpaid or dmg_unpaid or tax_unpaid) else 'paid'

    # ===== วันที่/วันครบกำหนดชำระ ของแต่ละประเภท (คำนวณจากรายการล่าสุด + 14 วัน) =====
    invoice_report_date = fields.Date(string='วันที่ (ใบแจ้งหนี้)',
        compute='_compute_report_dates', store=True)
    invoice_due_date = fields.Date(string='วันที่กำหนดชำระ (ใบแจ้งหนี้)',
        compute='_compute_report_dates', store=True)
    lost_report_date = fields.Date(string='วันที่ (ค่าปรับหาย)',
        compute='_compute_report_dates', store=True)
    lost_due_date = fields.Date(string='วันที่กำหนดชำระ (ค่าปรับหาย)',
        compute='_compute_report_dates', store=True)
    damage_report_date = fields.Date(string='วันที่ (ค่าปรับชำรุด)',
        compute='_compute_report_dates', store=True)
    damage_due_date = fields.Date(string='วันที่กำหนดชำระ (ค่าปรับชำรุด)',
        compute='_compute_report_dates', store=True)
    tax_report_date = fields.Date(string='วันที่ (Tax)',
        compute='_compute_report_dates', store=True)
    tax_due_date = fields.Date(string='วันที่กำหนดชำระ (Tax)',
        compute='_compute_report_dates', store=True)

    @api.depends('customer_invoice_line_ids.invoice_date',
                 'customer_penalty_line_ids.rental_start_date',
                 'customer_damage_line_ids.rental_start_date',
                 'customer_tax_line_ids.invoice_date')
    def _compute_report_dates(self):
        for rec in self:
            inv_dates = [l.invoice_date for l in rec.customer_invoice_line_ids if l.invoice_date]
            rec.invoice_report_date = max(inv_dates) if inv_dates else False
            rec.invoice_due_date = (rec.invoice_report_date + timedelta(days=14)) if rec.invoice_report_date else False

            # ค่าปรับหาย: วันที่ = วันที่ใบแจ้งหนี้ล่าสุด, วันกำหนดชำระ = +14 วัน
            pen_dates = [l.rental_start_date for l in rec.customer_penalty_line_ids if l.rental_start_date]
            rec.lost_report_date = max(pen_dates) if pen_dates else False
            rec.lost_due_date = (rec.lost_report_date + timedelta(days=14)) if rec.lost_report_date else False

            # ค่าปรับชำรุด: วันที่ = วันที่ใบแจ้งหนี้ล่าสุด, วันกำหนดชำระ = +14 วัน
            dmg_dates = [l.rental_start_date for l in rec.customer_damage_line_ids if l.rental_start_date]
            rec.damage_report_date = max(dmg_dates) if dmg_dates else False
            rec.damage_due_date = (rec.damage_report_date + timedelta(days=14)) if rec.damage_report_date else False

            tax_dates = [l.invoice_date for l in rec.customer_tax_line_ids if l.invoice_date]
            rec.tax_report_date = max(tax_dates) if tax_dates else False
            rec.tax_due_date = (rec.tax_report_date + timedelta(days=14)) if rec.tax_report_date else False

    @api.depends('customer_amount_residual', 'customer_penalty_residual',
                 'customer_damage_residual', 'customer_tax_residual')
    def _compute_grand_total(self):
        for rec in self:
            rec.grand_total = (rec.customer_amount_residual + rec.customer_penalty_residual
                               + rec.customer_damage_residual + rec.customer_tax_residual)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') in (False, 'New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('npd.debt.summary') or 'New'
        return super().create(vals)

    # ===== baht text (สำหรับรายงาน) =====
    def _baht(self, amount):
        if bahttext:
            return bahttext(amount or 0.0)
        return '{:,.2f} บาท'.format(amount or 0.0)

    def get_total_baht_text_sheet(self):
        return self._baht(self.customer_amount_residual)

    def get_lost_baht_text_sheet(self):
        return self._baht(self.customer_penalty_residual)

    def get_damage_baht_text_sheet(self):
        return self._baht(self.customer_damage_residual)

    def get_total_baht_text_sheet_tax(self):
        return self._baht(self.customer_tax_residual)

    def get_amount_residual_formatted(self):
        return '{:,.2f}'.format(self.customer_amount_residual)

    def get_amount_lost_formatted(self):
        return '{:,.2f}'.format(self.customer_penalty_residual)

    def get_amount_damage_formatted(self):
        return '{:,.2f}'.format(self.customer_damage_residual)

    def get_amount_tax_formatted(self):
        return '{:,.2f}'.format(self.customer_tax_residual)

    # =========================================================================
    #  ค้นหาลูกค้าที่เข้าเงื่อนไข + สร้าง/อัพเดท record  (เรียกจากเมนู/ปุ่มอัพเดท)
    # =========================================================================
    @api.model
    def _get_overdue_partner_ids(self):
        """คืน commercial partner ids ที่มีใบแจ้งหนี้ลูกค้าค้างชำระ (ไม่ว่าถึงกำหนดหรือยัง)"""
        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('amount_residual', '>', 0),
            ('invoice_date', '>=', DEBT_START_STR),
        ])
        partner_ids = set()
        for inv in invoices:
            p = inv.partner_id.commercial_partner_id or inv.partner_id
            if p:
                partner_ids.add(p.id)
        return list(partner_ids)

    @api.model
    def cron_refresh_all(self):
        """อัพเดทข้อมูลทุกลูกค้า (เรียกจาก Scheduled Action ทุกวันตี 3)"""
        self._refresh_all_records()

    @api.model
    def action_refresh_all(self):
        """อัพเดททั้งหมดแล้วเปิดรายการ (สำหรับเรียกเองเมื่อต้องการ)"""
        self._refresh_all_records()
        return {
            'type': 'ir.actions.act_window',
            'name': _('รวมหนี้ลูกค้า'),
            'res_model': 'npd.debt.summary',
            'view_mode': 'tree,form',
            'search_view_id': self.env.ref('npd_debt_summary.npd_debt_summary_view_search').id,
            'context': {'search_default_group_customer': 1},
            'target': 'current',
        }

    @api.model
    def _refresh_all_records(self):
        """สแกน + อัพเดทข้อมูล 4 แท็บของทุกลูกค้า (ไม่ลบลูกค้า — ใช้สถานะแทน)"""
        # ลูกค้าที่มีใบแจ้งหนี้ค้างชำระ (สำหรับเพิ่มลูกค้าใหม่) + ลูกค้าที่มีอยู่แล้ว (อัพเดทซ้ำ)
        partner_ids = set(self._get_overdue_partner_ids())
        existing = self.search([])
        by_customer = {r.customer_id.id: r for r in existing}
        all_ids = partner_ids | set(by_customer.keys())

        for pid in all_ids:
            rec = by_customer.get(pid)
            if not rec:
                rec = self.create({'customer_id': pid})
            rec._populate_customer_data()
        # หมายเหตุ: ไม่ลบลูกค้าที่จ่ายครบแล้ว — เก็บไว้และแสดงสถานะ "ชำระแล้ว" แทน
        # แต่ล้างลูกค้าที่ไม่มีรายการเหลือเลย (เช่น มีแต่หนี้ปีเก่าต่ำกว่า 2026)
        self._remove_empty_records()

    @api.model
    def _remove_empty_records(self):
        """ลบ record ที่ไม่มีรายการหนี้ทั้ง 4 ประเภทเลย
        (ลูกค้าที่มีเฉพาะข้อมูลปีต่ำกว่า 2026 จะถูกล้างออกหลังกรองข้อมูล)"""
        empty = self.search([]).filtered(
            lambda r: not (r.customer_invoice_line_ids or r.customer_penalty_line_ids
                           or r.customer_damage_line_ids or r.customer_tax_line_ids))
        if empty:
            empty.unlink()

    @api.model
    def action_clear_old_data(self):
        """ล้างข้อมูลหนี้ปีเก่า (ต่ำกว่า 2026) ออกทั้งหมด แล้วดึงข้อมูลใหม่ตั้งแต่ปี 2026
        เรียกครั้งเดียวเพื่อล้างข้อมูลเดิมที่มีอยู่ในระบบ"""
        self._refresh_all_records()
        return True

    def action_refresh_one(self):
        """ปุ่มอัพเดทข้อมูลลูกค้ารายนี้"""
        for rec in self:
            rec._populate_customer_data()
        return True

    def _populate_customer_data(self):
        """ดึงข้อมูลหนี้ทั้ง 4 ประเภทของลูกค้ารายนี้มาเก็บเป็น record จริง"""
        self.ensure_one()
        customer = self.customer_id
        if not customer:
            return
        today = date.today()
        commercial = customer.commercial_partner_id or customer

        # ============ 1) ใบแจ้งหนี้ (เก็บใบเดิมไว้ด้วย เพื่อแสดงสถานะ ค้าง/จ่ายแล้ว) ============
        existing_inv_ids = set(self.customer_invoice_line_ids.mapped('invoice_id').ids)
        unpaid_invoices = self.env['account.move'].search([
            ('partner_id', 'child_of', commercial.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0),
            ('invoice_date', '>=', DEBT_START_STR),
        ])
        # กรองเฉพาะปี 2026 เป็นต้นไป (ใบเดิมที่เก็บไว้แต่เป็นปีเก่าจะถูกตัดออก = ล้างข้อมูลเก่า)
        invoices = self.env['account.move'].browse(
            sorted(existing_inv_ids | set(unpaid_invoices.ids))).exists().filtered(
            lambda m: m.move_type == 'out_invoice'
            and m.invoice_date and m.invoice_date >= DEBT_START_DATE)
        inv_lines = [(5, 0, 0)]
        total_residual = 0.0
        for inv in invoices:
            inv.invalidate_cache(['amount_residual', 'payment_state'], [inv.id])
            residual = inv.amount_residual
            total_residual += residual
            payment_label = dict(
                self.env['account.move']._fields['payment_state'].selection
            ).get(inv.payment_state, inv.payment_state)
            days_over = (today - inv.invoice_date_due).days if inv.invoice_date_due else 0
            inv_product_html = self._build_product_html(inv)
            inv_lines.append((0, 0, {
                'invoice_id': inv.id,
                'invoice_name': inv.name,
                'invoice_origin': inv.invoice_origin or '',
                'invoice_date': inv.invoice_date,
                'invoice_date_due': inv.invoice_date_due,
                'amount_total': inv.amount_total,
                'amount_residual': residual,
                'payment_state': inv.payment_state,
                'payment_state_label': payment_label,
                'days_overdue': days_over,
                'product_info_html': inv_product_html,
            }))

        # ============ 2) ค่าปรับหาย (เก็บใบเดิมไว้ด้วย) ============
        existing_pen_ids = set(self.customer_penalty_line_ids.mapped('invoice_id').ids)
        lost_reason = self.env['scrap.reason.code'].search([('name', '=', 'สินค้าหาย')], limit=1)
        penalty_lines = [(5, 0, 0)]
        total_penalty_residual = 0.0
        new_pen_ids = set(self.env['account.move'].search([
            ('partner_id', 'child_of', commercial.id),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0),
            ('reason_code_id', '=', lost_reason.id),
            ('invoice_date', '>=', DEBT_START_STR),
        ]).ids) if lost_reason else set()
        penalty_invoices = self.env['account.move'].browse(sorted(existing_pen_ids | new_pen_ids)).exists().filtered(
            lambda m: m.invoice_date and m.invoice_date >= DEBT_START_DATE)
        if penalty_invoices:
            for pinv in penalty_invoices:
                pinv.invalidate_cache(['amount_residual'], [pinv.id])
                p_residual = pinv.amount_residual
                total_penalty_residual += p_residual
                branch_name = pinv.branch_id.name or '' if getattr(pinv, 'branch_id', False) else ''
                sales_name = pinv.sales_contact_id.name or '' if getattr(pinv, 'sales_contact_id', False) else ''
                rental_start, rental_end = self._get_rental_dates(pinv)
                penalty_amt = getattr(pinv, 'amount_price_subtotal_without_discount', 0.0) or 0.0
                if not penalty_amt:
                    penalty_amt = sum(
                        l.quantity * l.price_unit for l in pinv.invoice_line_ids
                        if not l.exclude_from_invoice_tab)
                discount_amt = (getattr(pinv, 'discount_amt_line', 0.0) or 0.0)
                discount_amt += (getattr(pinv, 'discount_amt', 0.0) or 0.0)
                net_penalty = pinv.amount_total
                amount_paid = pinv.amount_total - p_residual
                product_html, product_line_vals = self._build_product_html_and_lines(pinv)
                penalty_lines.append((0, 0, {
                    'invoice_id': pinv.id,
                    'invoice_name': pinv.name,
                    'branch_name': branch_name,
                    'sales_contact_name': sales_name,
                    'rental_start_date': pinv.invoice_date,
                    'rental_end_date': pinv.invoice_date_due,
                    'penalty_amount': penalty_amt,
                    'discount_amount': discount_amt,
                    'net_penalty': net_penalty,
                    'amount_paid': amount_paid,
                    'amount_residual': p_residual,
                    'product_info_html': product_html,
                    'penalty_product_line_ids': product_line_vals,
                }))

        # ============ 3) ค่าปรับชำรุด (เก็บใบเดิมไว้ด้วย) ============
        existing_dmg_ids = set(self.customer_damage_line_ids.mapped('invoice_id').ids)
        damage_reason = self.env['scrap.reason.code'].search([('name', '=', 'สินค้าชำรุด')], limit=1)
        damage_lines = [(5, 0, 0)]
        total_damage_residual = 0.0
        new_dmg_ids = set(self.env['account.move'].search([
            ('partner_id', 'child_of', commercial.id),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0),
            ('reason_code_id', '=', damage_reason.id),
            ('invoice_date', '>=', DEBT_START_STR),
        ]).ids) if damage_reason else set()
        damage_invoices = self.env['account.move'].browse(sorted(existing_dmg_ids | new_dmg_ids)).exists().filtered(
            lambda m: m.invoice_date and m.invoice_date >= DEBT_START_DATE)
        if damage_invoices:
            for dinv in damage_invoices:
                dinv.invalidate_cache(['amount_residual'], [dinv.id])
                d_residual = dinv.amount_residual
                total_damage_residual += d_residual
                d_branch_name = dinv.branch_id.name or '' if getattr(dinv, 'branch_id', False) else ''
                d_sales_name = dinv.sales_contact_id.name or '' if getattr(dinv, 'sales_contact_id', False) else ''
                d_rental_start, d_rental_end = self._get_rental_dates(dinv)
                d_penalty_amt = getattr(dinv, 'amount_price_subtotal_without_discount', 0.0) or 0.0
                if not d_penalty_amt:
                    d_penalty_amt = sum(
                        l.quantity * l.price_unit for l in dinv.invoice_line_ids
                        if not l.exclude_from_invoice_tab)
                d_discount_amt = (getattr(dinv, 'discount_amt_line', 0.0) or 0.0)
                d_discount_amt += (getattr(dinv, 'discount_amt', 0.0) or 0.0)
                d_net_penalty = dinv.amount_total
                d_amount_paid = dinv.amount_total - d_residual
                d_product_html = self._build_product_html(dinv)
                damage_lines.append((0, 0, {
                    'invoice_id': dinv.id,
                    'invoice_name': dinv.name,
                    'branch_name': d_branch_name,
                    'sales_contact_name': d_sales_name,
                    'rental_start_date': dinv.invoice_date,
                    'rental_end_date': dinv.invoice_date_due,
                    'damage_amount': d_penalty_amt,
                    'discount_amount': d_discount_amt,
                    'net_damage': d_net_penalty,
                    'amount_paid': d_amount_paid,
                    'amount_residual': d_residual,
                    'product_info_html': d_product_html,
                }))

        # ============ 4) ค่า Tax (ภาษีหัก ณ ที่จ่าย) ============
        tax_lines = [(5, 0, 0)]
        total_tax_amount = 0.0
        seen_tax_pairs = set()

        candidate_invoices = self.env['account.move'].search([
            ('partner_id', 'child_of', commercial.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', DEBT_START_STR),
        ])
        for tinv in candidate_invoices:
            payment_inv_lines = self.env['account.payment.invoice'].search([
                ('invoice_id', '=', tinv.id),
                ('payment_id.state', '=', 'posted'),
            ])
            for pi_line in payment_inv_lines:
                payment = pi_line.payment_id
                if not payment:
                    continue
                if not getattr(payment, 'wht_has_slip', False):
                    continue
                pair_key = (tinv.id, payment.id)
                # วิธี A: หาจาก paid_ids (payment method ชื่อ "ภาษี...หัก...")
                for paid_line in payment.paid_ids:
                    method_name = (paid_line.payment_method_id.name or '').strip() if paid_line.payment_method_id else ''
                    if method_name and 'ภาษี' in method_name and 'หัก' in method_name:
                        if pair_key in seen_tax_pairs:
                            continue
                        seen_tax_pairs.add(pair_key)
                        tax_amt = paid_line.total or 0.0
                        total_tax_amount += tax_amt
                        tax_lines.append((0, 0, self._prepare_tax_line_vals(tinv, payment, tax_amt)))
                # วิธี B: หาจาก wt_cert_ids (หนังสือรับรองหัก ณ ที่จ่าย)
                for wht_cert in payment.wt_cert_ids:
                    if pair_key in seen_tax_pairs:
                        continue
                    wht_amt = wht_cert.tax_amount or 0.0
                    if wht_amt > 0:
                        seen_tax_pairs.add(pair_key)
                        total_tax_amount += wht_amt
                        tax_lines.append((0, 0, self._prepare_tax_line_vals(tinv, payment, wht_amt)))

        # ============ เขียนข้อมูลทั้งหมดลง record ============
        self.write({
            'partner_name': customer.name or '',
            'partner_phone': customer.phone or '',
            'partner_mobile': customer.mobile or '',
            'partner_email': customer.email or '',
            'partner_vat': customer.vat or '',
            'partner_street': customer.street or '',
            'partner_street2': customer.street2 or '',
            'partner_city': customer.city or '',
            'partner_state_id': customer.state_id.id if customer.state_id else False,
            'partner_zip': customer.zip or '',
            'customer_invoice_line_ids': inv_lines,
            'customer_penalty_line_ids': penalty_lines,
            'customer_damage_line_ids': damage_lines,
            'customer_tax_line_ids': tax_lines,
            'last_update': fields.Datetime.now(),
        })

    # ------------------------------------------------------------------ helpers
    def _get_rental_dates(self, inv):
        """ดึงวันเริ่มเช่า/วันคืน จาก stock.picking ที่อ้างอิงเอกสารนี้"""
        rental_start = False
        rental_end = False
        if inv.invoice_origin:
            picking = self.env['stock.picking'].search([
                ('origin', '=', inv.invoice_origin)], limit=1, order='id desc')
            if not picking:
                picking = self.env['stock.picking'].search([
                    ('name', '=', inv.invoice_origin)], limit=1)
            if picking:
                rental_start = picking.start_x_date if hasattr(picking, 'start_x_date') else False
                rental_end = picking.end_x_date if hasattr(picking, 'end_x_date') else False
        return rental_start, rental_end

    def _build_product_html(self, inv):
        """สร้าง HTML table แสดงรายการสินค้าของใบแจ้งหนี้"""
        html = '<table class="table table-sm table-bordered" style="width:100%">'
        html += '<thead><tr style="background:#f5f5f5">'
        html += '<th>สินค้า</th><th>รายละเอียด</th>'
        html += '<th style="text-align:right">จำนวน</th>'
        html += '<th style="text-align:right">ราคาต่อหน่วย</th>'
        html += '<th style="text-align:right">ส่วนลด (%)</th>'
        html += '<th style="text-align:right">ยอดรวม</th>'
        html += '</tr></thead><tbody>'
        has_lines = False
        for line in inv.invoice_line_ids:
            if line.exclude_from_invoice_tab:
                continue
            has_lines = True
            pname = line.product_id.name if line.product_id else ''
            html += '<tr>'
            html += '<td>%s</td>' % pname
            html += '<td>%s</td>' % (line.name or '')
            html += '<td style="text-align:right">%.2f</td>' % line.quantity
            html += '<td style="text-align:right">{:,.2f}</td>'.format(line.price_unit)
            html += '<td style="text-align:right">%.2f</td>' % line.discount
            html += '<td style="text-align:right">{:,.2f}</td>'.format(line.price_subtotal)
            html += '</tr>'
        if not has_lines:
            html += '<tr><td colspan="6" style="text-align:center;color:#999">ไม่มีรายการสินค้า</td></tr>'
        html += '</tbody></table>'
        return html

    def _build_product_html_and_lines(self, inv):
        """สร้าง HTML table + product line vals (สำหรับค่าปรับหาย)"""
        html = '<table class="table table-sm table-bordered" style="width:100%">'
        html += '<thead><tr style="background:#f5f5f5">'
        html += '<th>สินค้า</th><th>รายละเอียด</th>'
        html += '<th style="text-align:right">จำนวน</th>'
        html += '<th style="text-align:right">ราคาต่อหน่วย</th>'
        html += '<th style="text-align:right">ส่วนลด (%)</th>'
        html += '<th style="text-align:right">ยอดรวม</th>'
        html += '</tr></thead><tbody>'
        has_lines = False
        product_line_vals = []
        for line in inv.invoice_line_ids:
            if line.exclude_from_invoice_tab:
                continue
            has_lines = True
            pname = line.product_id.name if line.product_id else ''
            html += '<tr>'
            html += '<td>%s</td>' % pname
            html += '<td>%s</td>' % (line.name or '')
            html += '<td style="text-align:right">%.2f</td>' % line.quantity
            html += '<td style="text-align:right">{:,.2f}</td>'.format(line.price_unit)
            html += '<td style="text-align:right">%.2f</td>' % line.discount
            html += '<td style="text-align:right">{:,.2f}</td>'.format(line.price_subtotal)
            html += '</tr>'
            product_line_vals.append((0, 0, {
                'product_name': pname,
                'description': line.name or '',
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'price_subtotal': line.price_subtotal,
            }))
        if not has_lines:
            html += '<tr><td colspan="6" style="text-align:center;color:#999">ไม่มีรายการสินค้า</td></tr>'
        html += '</tbody></table>'
        return html, product_line_vals

    def _prepare_tax_line_vals(self, invoice, payment, tax_amt):
        """สร้าง dict สำหรับ tax line record"""
        return {
            'invoice_id': invoice.id,
            'invoice_name': invoice.name,
            'invoice_origin': invoice.invoice_origin or '',
            'invoice_date': invoice.invoice_date,
            'invoice_date_due': invoice.invoice_date_due,
            'amount_total': invoice.amount_total,
            'payment_id': payment.id,
            'payment_name': payment.name or '',
            'tax_amount': tax_amt,
            'product_info_html': self._build_product_html(invoice),
        }


class NpdDebtSummaryInvoiceLine(models.Model):
    _name = 'npd.debt.summary.invoice.line'
    _description = 'รายการใบแจ้งหนี้ค้างชำระ (สรุปหนี้)'
    _order = 'invoice_date_due asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขที่ใบแจ้งหนี้', related='invoice_id.name', store=True, readonly=True)
    invoice_origin = fields.Char(string='อ้างอิง SO')
    invoice_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    invoice_date_due = fields.Date(string='วันกำหนดจ่าย')
    amount_total = fields.Float(string='รวม', digits=(16, 2))
    amount_residual = fields.Float(string='ยอดเงินค้างชำระ', digits=(16, 2))
    payment_state = fields.Char(string='สถานะ (code)')
    payment_state_label = fields.Char(string='สถานะการชำระเงิน')
    days_overdue = fields.Integer(string='จำนวนวันที่เกิน')
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('amount_residual')
    def _compute_payment_status(self):
        for l in self:
            l.payment_status = 'paid' if (l.amount_residual or 0.0) <= 0.005 else 'unpaid'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('ใบแจ้งหนี้ค้างชำระ'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class NpdDebtSummaryPenaltyLine(models.Model):
    _name = 'npd.debt.summary.penalty.line'
    _description = 'รายการค่าปรับหาย (สรุปหนี้)'
    _order = 'invoice_name asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขเอกสาร', related='invoice_id.name', store=True, readonly=True)
    branch_name = fields.Char(string='สาขา')
    sales_contact_name = fields.Char(string='เซลล์')
    rental_start_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    rental_end_date = fields.Date(string='วันกำหนดจ่าย')
    penalty_amount = fields.Float(string='ค่าปรับหาย', digits=(16, 2))
    discount_amount = fields.Float(string='ส่วนลด', digits=(16, 2))
    net_penalty = fields.Float(string='ปรับหายสุทธิ', digits=(16, 2))
    amount_paid = fields.Float(string='รับชำระ', digits=(16, 2))
    amount_residual = fields.Float(string='คงเหลือ', digits=(16, 2))
    penalty_product_line_ids = fields.One2many(
        'npd.debt.summary.penalty.product.line', 'penalty_line_id', string='รายการสินค้า')
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('amount_residual')
    def _compute_payment_status(self):
        for l in self:
            l.payment_status = 'paid' if (l.amount_residual or 0.0) <= 0.005 else 'unpaid'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('ใบแจ้งหนี้ค่าปรับหาย'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class NpdDebtSummaryPenaltyProductLine(models.Model):
    _name = 'npd.debt.summary.penalty.product.line'
    _description = 'รายการสินค้าค่าปรับหาย (สรุปหนี้)'

    penalty_line_id = fields.Many2one('npd.debt.summary.penalty.line', string='รายการค่าปรับหาย', ondelete='cascade')
    product_name = fields.Char(string='สินค้า')
    description = fields.Char(string='รายละเอียด')
    quantity = fields.Float(string='จำนวน', digits=(16, 2))
    price_unit = fields.Float(string='ราคาต่อหน่วย', digits=(16, 2))
    discount = fields.Float(string='ส่วนลด (%)', digits=(16, 2))
    price_subtotal = fields.Float(string='ยอดรวม', digits=(16, 2))


class NpdDebtSummaryDamageLine(models.Model):
    _name = 'npd.debt.summary.damage.line'
    _description = 'รายการค่าปรับชำรุด (สรุปหนี้)'
    _order = 'invoice_name asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขเอกสาร', related='invoice_id.name', store=True, readonly=True)
    branch_name = fields.Char(string='สาขา')
    sales_contact_name = fields.Char(string='เซลล์')
    rental_start_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    rental_end_date = fields.Date(string='วันกำหนดจ่าย')
    damage_amount = fields.Float(string='ค่าปรับชำรุด', digits=(16, 2))
    discount_amount = fields.Float(string='ส่วนลด', digits=(16, 2))
    net_damage = fields.Float(string='ปรับชำรุดสุทธิ', digits=(16, 2))
    amount_paid = fields.Float(string='รับชำระ', digits=(16, 2))
    amount_residual = fields.Float(string='คงเหลือ', digits=(16, 2))
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('amount_residual')
    def _compute_payment_status(self):
        for l in self:
            l.payment_status = 'paid' if (l.amount_residual or 0.0) <= 0.005 else 'unpaid'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('ใบแจ้งหนี้ค่าปรับชำรุด'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class NpdDebtSummaryTaxLine(models.Model):
    _name = 'npd.debt.summary.tax.line'
    _description = 'รายการค่า Tax (สรุปหนี้)'
    _order = 'invoice_name asc'

    summary_id = fields.Many2one('npd.debt.summary', string='สรุปหนี้', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขที่ใบแจ้งหนี้', related='invoice_id.name', store=True, readonly=True)
    invoice_origin = fields.Char(string='อ้างอิง SO')
    invoice_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    invoice_date_due = fields.Date(string='วันกำหนดจ่าย')
    amount_total = fields.Float(string='ยอดรวมใบแจ้งหนี้', digits=(16, 2))
    payment_id = fields.Many2one('account.payment', string='รับชำระ')
    payment_name = fields.Char(string='เลขที่รับชำระ')
    tax_amount = fields.Float(string='ยอด Tax', digits=(16, 2))
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)
    payment_status = fields.Selection([('unpaid', 'ค้างชำระ'), ('paid', 'จ่ายแล้ว')],
        string='สถานะ', compute='_compute_payment_status', store=True)

    @api.depends('invoice_id.amount_residual')
    def _compute_payment_status(self):
        for l in self:
            resid = l.invoice_id.amount_residual if l.invoice_id else 0.0
            l.payment_status = 'paid' if (resid or 0.0) <= 0.005 else 'unpaid'

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('ใบแจ้งหนี้'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
