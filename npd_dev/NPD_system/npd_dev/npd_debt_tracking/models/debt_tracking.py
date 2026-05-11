# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, date, timedelta
import base64
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

_logger = logging.getLogger(__name__)


class NpdDebtTracking(models.Model):
    _name = 'npd.debt.tracking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'ติดตามหนี้'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    name = fields.Char(string='เลขที่เอกสาร', default='New', readonly=True, copy=False, index=True)
    display_name = fields.Char(string='ชื่อ', compute='_compute_display_name', store=True)

    @api.depends('name', 'sale_id', 'partner_id')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.name and rec.name != 'New':
                parts.append(rec.name)
            if rec.sale_id:
                parts.append(rec.sale_id.name)
            if rec.partner_id:
                parts.append(rec.partner_id.name)
            rec.display_name = ' - '.join(parts) if parts else 'New'

    # debt_type = fields.Selection([
    #     ('odoo', 'ลูกหนี้ Odoo'),
    #     ('baankhiew', 'ลูกหนี้บ้านเขียว'),
    # ], string='ประเภทลูกหนี้', default='odoo', required=True, tracking=True)
    
    company_id = fields.Many2one('res.company', string='บริษัท',
        default=lambda self: self.env.company, readonly=True)

    # ฟิลด์ชื่อลูกค้าที่เลือกได้อิสระ - ดึงลูกค้าทั้งหมดมาแสดง
    customer_id = fields.Many2one('res.partner', string='ชื่อลูกค้า',
        domain="[('customer_rank', '>', 0)]",
        required=True,
        help='เลือกลูกค้าจากรายชื่อในระบบ')

    # ฟิลด์เก็บรายการ SO ที่มียอดค้างชำระของลูกค้าที่เลือก
    sale_order_ids = fields.Many2many('sale.order', string='รายการใบสั่งขาย',
        compute='_compute_sale_order_ids', store=False)

    sale_id = fields.Many2one('sale.order', string='ใบสั่งขาย',
        domain="[('id', 'in', sale_order_ids)]")

    @api.model
    def _get_sale_orders_with_unpaid_invoices(self):
        """คืนค่า sale order ids ที่มีใบแจ้งหนี้ค้างชำระเกิน 45 วัน"""
        # คำนวณวันที่ 45 วันก่อน
        date_45_days_ago = date.today() - timedelta(days=45)
        # หา invoice ที่ค้างชำระและเกินกำหนด >= 45 วัน (ทุกประเภทใบแจ้งหนี้)
        invoices = self.env['account.move'].search([
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('amount_residual', '>', 0),
            ('invoice_date_due', '<=', date_45_days_ago),
        ])
        
        # หา sale order จาก 2 แหล่ง:
        # 1. จาก invoice_line_ids.sale_line_ids (วิธีปกติ)
        sale_order_ids = set(invoices.mapped('invoice_line_ids.sale_line_ids.order_id').ids)
        
        # 2. จาก invoice_origin (Source Document) สำหรับใบแจ้งหนี้ที่ไม่ได้สร้างจาก SO โดยตรง เช่น INS
        for inv in invoices:
            if inv.invoice_origin:
                # หา SO จาก invoice_origin (อาจมีหลาย SO คั่นด้วย comma)
                origins = [o.strip() for o in inv.invoice_origin.split(',')]
                for origin in origins:
                    so = self.env['sale.order'].search([('name', '=', origin)], limit=1)
                    if so:
                        sale_order_ids.add(so.id)
        
        return list(sale_order_ids)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """Override เพื่อเพิ่ม domain สำหรับ sale_id ให้แสดงเฉพาะใบสั่งขายที่มีใบแจ้งหนี้ค้างชำระ"""
        res = super(NpdDebtTracking, self).fields_view_get(view_id=view_id, view_type=view_type,
                                                           toolbar=toolbar, submenu=submenu)
        if view_type == 'form' and 'sale_id' in res.get('fields', {}):
            sale_order_ids = self._get_sale_orders_with_unpaid_invoices()
            res['fields']['sale_id']['domain'] = [('id', 'in', sale_order_ids)]
        return res
    partner_id = fields.Many2one(related='sale_id.partner_id', string='ลูกค้า', store=True)
    partner_name = fields.Char(related='partner_id.name', string='ชื่อลูกค้า', store=True)
    partner_phone = fields.Char(string='เบอร์โทรศัพท์', store=True)
    partner_mobile = fields.Char(string='มือถือ', store=True)
    partner_email = fields.Char(string='อีเมล', store=True)
    partner_street = fields.Char(string='ที่อยู่', store=True)
    partner_street2 = fields.Char(string='ที่อยู่ 2', store=True)
    partner_city = fields.Char(string='เมือง', store=True)
    partner_state_id = fields.Many2one('res.country.state', string='จังหวัด', store=True)
    partner_zip = fields.Char(string='รหัสไปรษณีย์', store=True)
    partner_vat = fields.Char(string='เลขที่ผู้เสียภาษี', store=True)

    invoice_ids = fields.Many2many('account.move', string='ใบแจ้งหนี้ค้างชำระ',
        compute='_compute_invoice_info', store=False)

    # ใบแจ้งหนี้ค้างชำระทั้งหมดของลูกค้า (One2many เพื่อส่งข้อมูลตรงจาก server)
    customer_invoice_line_ids = fields.One2many('npd.debt.tracking.invoice.line',
        'tracking_id', string='ใบแจ้งหนี้ค้างชำระทั้งหมด')
    customer_amount_residual = fields.Monetary(string='ยอดค้างชำระทั้งหมด',
        currency_field='currency_id')

    # ค่าปรับหายทั้งหมดของลูกค้า (One2many)
    customer_penalty_line_ids = fields.One2many('npd.debt.tracking.penalty.line',
        'tracking_id', string='ค่าปรับหายทั้งหมด')
    customer_penalty_residual = fields.Monetary(string='ค้างชำระค่าปรับหาย',
        currency_field='currency_id')

    # ค่าปรับชำรุดทั้งหมดของลูกค้า (One2many)
    customer_damage_line_ids = fields.One2many('npd.debt.tracking.damage.line',
        'tracking_id', string='ค่าปรับชำรุดทั้งหมด')
    customer_damage_residual = fields.Monetary(string='ค้างชำระค่าปรับชำรุด',
        currency_field='currency_id')

    # ค่า Tax (ภาษีหัก ณ ที่จ่าย) ทั้งหมดของลูกค้า (One2many)
    customer_tax_line_ids = fields.One2many('npd.debt.tracking.tax.line',
        'tracking_id', string='ค่า Tax ทั้งหมด')
    customer_tax_residual = fields.Monetary(string='ค้างชำระค่า Tax',
        currency_field='currency_id')

    # ฟิลด์ใบแจ้งหนี้ที่เลือกได้ - แสดงเฉพาะใบแจ้งหนี้ค้างชำระของ SO ที่เลือก
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้',
        domain="[('id', 'in', invoice_ids)]",
        help='เลือกใบแจ้งหนี้ค้างชำระ')
    currency_id = fields.Many2one(related='sale_id.currency_id', string='สกุลเงิน', store=True)
    amount_total = fields.Monetary(related='sale_id.amount_total', string='ยอดรวมทั้งหมด',
        currency_field='currency_id', store=True)
    amount_residual = fields.Monetary(string='ยอดค้างชำระ', currency_field='currency_id',
        compute='_compute_invoice_info', store=False)
    
    # ฟิลด์วันครบกำหนดชำระจากใบแจ้งหนี้ที่เลือก
    invoice_date_due = fields.Date(related='invoice_id.invoice_date_due', string='วันครบกำหนดชำระ', store=False)
    
    # ฟิลด์แสดงจำนวนวันที่เกินกำหนดหรือเหลืออีกกี่วัน
    days_due_display = fields.Char(string='วันครบกำหนดชำระ', compute='_compute_days_due_display', store=False)
    
    @api.depends('invoice_date_due')
    def _compute_days_due_display(self):
        today = date.today()
        for rec in self:
            if rec.invoice_date_due:
                delta = (today - rec.invoice_date_due).days
                if delta == 0:
                    rec.days_due_display = 'วันนี้'
                elif delta == 1:
                    rec.days_due_display = 'เมื่อวาน'
                elif delta > 1:
                    rec.days_due_display = '%d วันที่แล้ว' % delta
                elif delta == -1:
                    rec.days_due_display = 'พรุ่งนี้'
                else:
                    rec.days_due_display = 'อีก %d วัน' % abs(delta)
            else:
                rec.days_due_display = ''
    
    state = fields.Selection([
        ('draft', 'รอดำเนินการ'),
        ('in_progress', 'กำลังติดตาม'),
        ('done', 'เสร็จสิ้น'),
        ('cancel', 'ยกเลิก')
    ], string='สถานะ', default='draft', tracking=True)
    
    note = fields.Text(string='หมายเหตุ')
    
    call_log_ids = fields.One2many('npd.debt.tracking.call.log', 'tracking_id', string='ประวัติการโทร')
    call_count = fields.Integer(string='จำนวนครั้งที่โทร', compute='_compute_call_count')
    
    # Email Log
    email_log_ids = fields.One2many('npd.debt.tracking.email.log', 'tracking_id', string='ประวัติการส่งเมล')
    email_count = fields.Integer(string='จำนวนครั้งที่ส่งเมล', compute='_compute_email_count')

    @api.depends('customer_id')
    def _compute_sale_order_ids(self):
        """คำนวณรายการ SO ที่มียอดค้างชำระเกิน 45 วันของลูกค้าที่เลือก"""
        date_45_days_ago = date.today() - timedelta(days=45)
        for rec in self:
            if rec.customer_id:
                # หา invoice ที่ค้างชำระและเกินกำหนด >= 45 วัน (ทุกประเภทใบแจ้งหนี้)
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', rec.customer_id.id),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ('not_paid', 'partial')),
                    ('amount_residual', '>', 0),
                    ('invoice_date_due', '<=', date_45_days_ago),
                ])
                
                # หา sale order จาก 2 แหล่ง:
                # 1. จาก invoice_line_ids.sale_line_ids (วิธีปกติ)
                sale_order_ids = set(invoices.mapped('invoice_line_ids.sale_line_ids.order_id').ids)
                
                # 2. จาก invoice_origin (Source Document) สำหรับใบแจ้งหนี้ที่ไม่ได้สร้างจาก SO โดยตรง เช่น INS
                for inv in invoices:
                    if inv.invoice_origin:
                        origins = [o.strip() for o in inv.invoice_origin.split(',')]
                        for origin in origins:
                            so = self.env['sale.order'].search([('name', '=', origin)], limit=1)
                            if so:
                                sale_order_ids.add(so.id)
                
                rec.sale_order_ids = self.env['sale.order'].browse(list(sale_order_ids))
            else:
                rec.sale_order_ids = False

    @api.depends('sale_id')
    def _compute_invoice_info(self):
        date_45_days_ago = date.today() - timedelta(days=45)
        for rec in self:
            if rec.sale_id:
                # กรองเฉพาะใบแจ้งหนี้ที่เกินกำหนด >= 45 วัน (ทุกประเภท)
                # 1. หาจาก invoice_ids ของ SO (วิธีปกติ)
                invoices = rec.sale_id.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted' and
                    inv.payment_state in ('not_paid', 'partial') and
                    inv.invoice_date_due and inv.invoice_date_due <= date_45_days_ago)
                invoice_ids = set(invoices.ids)
                
                # 2. หาจาก invoice_origin ที่อ้างอิง SO นี้ (สำหรับ INS, etc.)
                additional_invoices = self.env['account.move'].search([
                    ('invoice_origin', 'ilike', rec.sale_id.name),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ('not_paid', 'partial')),
                    ('amount_residual', '>', 0),
                    ('invoice_date_due', '<=', date_45_days_ago),
                ])
                invoice_ids.update(additional_invoices.ids)
                
                all_invoices = self.env['account.move'].browse(list(invoice_ids))
                rec.invoice_ids = all_invoices
                rec.amount_residual = sum(all_invoices.mapped('amount_residual'))
            else:
                rec.invoice_ids = False
                rec.amount_residual = 0.0

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        """เมื่อเปลี่ยนลูกค้า ให้ดึงใบแจ้งหนี้ค้างชำระทั้งหมดมาแสดง"""
        self.sale_id = False
        self.invoice_id = False
        if self.customer_id:
            date_45_days_ago = date.today() - timedelta(days=45)
            commercial = self.customer_id.commercial_partner_id or self.customer_id
            # ค้นจาก amount_residual เป็นหลัก (>= 45 วัน)
            invoices = self.env['account.move'].search([
                ('partner_id', 'child_of', commercial.id),
                ('state', '=', 'posted'),
                ('amount_residual', '>', 0),
                ('invoice_date_due', '<=', date_45_days_ago),
            ])
            # สร้าง One2many virtual records — ข้อมูลฝังใน response ไม่ต้องให้ client อ่านเอง
            lines = [(5, 0, 0)]
            total_residual = 0.0
            for inv in invoices:
                inv.invalidate_cache(['amount_residual', 'payment_state'], [inv.id])
                residual = inv.amount_residual
                total_residual += residual
                payment_label = dict(
                    self.env['account.move']._fields['payment_state'].selection
                ).get(inv.payment_state, inv.payment_state)
                days_over = (date.today() - inv.invoice_date_due).days if inv.invoice_date_due else 0

                # === สร้าง HTML table แสดงรายการสินค้า (รองรับ virtual records) ===
                inv_product_html = '<table class="table table-sm table-bordered" style="width:100%">'
                inv_product_html += '<thead><tr style="background:#f5f5f5">'
                inv_product_html += '<th>สินค้า</th><th>รายละเอียด</th>'
                inv_product_html += '<th style="text-align:right">จำนวน</th>'
                inv_product_html += '<th style="text-align:right">ราคาต่อหน่วย</th>'
                inv_product_html += '<th style="text-align:right">ส่วนลด (%)</th>'
                inv_product_html += '<th style="text-align:right">ยอดรวม</th>'
                inv_product_html += '</tr></thead><tbody>'
                inv_has_lines = False
                for iline in inv.invoice_line_ids:
                    if iline.exclude_from_invoice_tab:
                        continue
                    inv_has_lines = True
                    i_pname = iline.product_id.name if iline.product_id else ''
                    inv_product_html += '<tr>'
                    inv_product_html += '<td>%s</td>' % i_pname
                    inv_product_html += '<td>%s</td>' % (iline.name or '')
                    inv_product_html += '<td style="text-align:right">%.2f</td>' % iline.quantity
                    inv_product_html += '<td style="text-align:right">{:,.2f}</td>'.format(iline.price_unit)
                    inv_product_html += '<td style="text-align:right">%.2f</td>' % iline.discount
                    inv_product_html += '<td style="text-align:right">{:,.2f}</td>'.format(iline.price_subtotal)
                    inv_product_html += '</tr>'
                if not inv_has_lines:
                    inv_product_html += '<tr><td colspan="6" style="text-align:center;color:#999">ไม่มีรายการสินค้า</td></tr>'
                inv_product_html += '</tbody></table>'

                lines.append((0, 0, {
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
            self.customer_invoice_line_ids = lines
            self.customer_amount_residual = total_residual

            # === ค้นหาใบแจ้งหนี้ค่าปรับหาย ===
            lost_reason = self.env['scrap.reason.code'].search([('name', '=', 'สินค้าหาย')], limit=1)
            penalty_lines = [(5, 0, 0)]
            total_penalty_residual = 0.0
            if lost_reason:
                penalty_invoices = self.env['account.move'].search([
                    ('partner_id', 'child_of', commercial.id),
                    ('state', '=', 'posted'),
                    ('amount_residual', '>', 0),
                    ('reason_code_id', '=', lost_reason.id),
                ])
                for pinv in penalty_invoices:
                    pinv.invalidate_cache(['amount_residual'], [pinv.id])
                    p_residual = pinv.amount_residual
                    total_penalty_residual += p_residual
                    # ดึงชื่อสาขา
                    branch_name = ''
                    if hasattr(pinv, 'branch_id') and pinv.branch_id:
                        branch_name = pinv.branch_id.name or ''
                    # ดึงชื่อเซลล์จาก sales_contact_id
                    sales_name = ''
                    if hasattr(pinv, 'sales_contact_id') and pinv.sales_contact_id:
                        sales_name = pinv.sales_contact_id.name or ''
                    # ดึงวันเริ่มเช่า/วันคืน จาก stock.picking
                    rental_start = False
                    rental_end = False
                    if pinv.invoice_origin:
                        picking = self.env['stock.picking'].search([
                            ('origin', '=', pinv.invoice_origin)
                        ], limit=1, order='id desc')
                        if not picking:
                            picking = self.env['stock.picking'].search([
                                ('name', '=', pinv.invoice_origin)
                            ], limit=1)
                        if picking:
                            rental_start = picking.start_x_date if hasattr(picking, 'start_x_date') else False
                            rental_end = picking.end_x_date if hasattr(picking, 'end_x_date') else False
                    # คำนวณยอดเงิน
                    penalty_amt = getattr(pinv, 'amount_price_subtotal_without_discount', 0.0) or 0.0
                    if not penalty_amt:
                        penalty_amt = sum(
                            l.quantity * l.price_unit
                            for l in pinv.invoice_line_ids
                            if not l.exclude_from_invoice_tab
                        )
                    discount_amt = getattr(pinv, 'discount_amt_line', 0.0) or 0.0
                    discount_amt += getattr(pinv, 'discount_amt', 0.0) or 0.0
                    net_penalty = pinv.amount_total
                    amount_paid = pinv.amount_total - p_residual

                    # === สร้าง HTML table แสดงรายการสินค้า + สร้าง product lines สำหรับ QWeb report ===
                    product_html = '<table class="table table-sm table-bordered" style="width:100%">'
                    product_html += '<thead><tr style="background:#f5f5f5">'
                    product_html += '<th>สินค้า</th><th>รายละเอียด</th>'
                    product_html += '<th style="text-align:right">จำนวน</th>'
                    product_html += '<th style="text-align:right">ราคาต่อหน่วย</th>'
                    product_html += '<th style="text-align:right">ส่วนลด (%)</th>'
                    product_html += '<th style="text-align:right">ยอดรวม</th>'
                    product_html += '</tr></thead><tbody>'
                    has_lines = False
                    product_line_vals = []
                    for line in pinv.invoice_line_ids:
                        if line.exclude_from_invoice_tab:
                            continue
                        has_lines = True
                        pname = line.product_id.name if line.product_id else ''
                        product_html += '<tr>'
                        product_html += '<td>%s</td>' % pname
                        product_html += '<td>%s</td>' % (line.name or '')
                        product_html += '<td style="text-align:right">%.2f</td>' % line.quantity
                        product_html += '<td style="text-align:right">{:,.2f}</td>'.format(line.price_unit)
                        product_html += '<td style="text-align:right">%.2f</td>' % line.discount
                        product_html += '<td style="text-align:right">{:,.2f}</td>'.format(line.price_subtotal)
                        product_html += '</tr>'
                        # สร้าง product line สำหรับ QWeb report
                        product_line_vals.append((0, 0, {
                            'product_name': pname,
                            'description': line.name or '',
                            'quantity': line.quantity,
                            'price_unit': line.price_unit,
                            'discount': line.discount,
                            'price_subtotal': line.price_subtotal,
                        }))
                    if not has_lines:
                        product_html += '<tr><td colspan="6" style="text-align:center;color:#999">ไม่มีรายการสินค้า</td></tr>'
                    product_html += '</tbody></table>'

                    penalty_lines.append((0, 0, {
                        'invoice_id': pinv.id,
                        'invoice_name': pinv.name,
                        'branch_name': branch_name,
                        'sales_contact_name': sales_name,
                        'rental_start_date': rental_start,
                        'rental_end_date': rental_end,
                        'penalty_amount': penalty_amt,
                        'discount_amount': discount_amt,
                        'net_penalty': net_penalty,
                        'amount_paid': amount_paid,
                        'amount_residual': p_residual,
                        'product_info_html': product_html,
                        'penalty_product_line_ids': product_line_vals,
                    }))
            self.customer_penalty_line_ids = penalty_lines
            self.customer_penalty_residual = total_penalty_residual

            # === ค้นหาใบแจ้งหนี้ค่าปรับชำรุด ===
            damage_reason = self.env['scrap.reason.code'].search([('name', '=', 'สินค้าชำรุด')], limit=1)
            damage_lines = [(5, 0, 0)]
            total_damage_residual = 0.0
            if damage_reason:
                damage_invoices = self.env['account.move'].search([
                    ('partner_id', 'child_of', commercial.id),
                    ('state', '=', 'posted'),
                    ('amount_residual', '>', 0),
                    ('reason_code_id', '=', damage_reason.id),
                ])
                for dinv in damage_invoices:
                    dinv.invalidate_cache(['amount_residual'], [dinv.id])
                    d_residual = dinv.amount_residual
                    total_damage_residual += d_residual
                    # ดึงชื่อสาขา
                    d_branch_name = ''
                    if hasattr(dinv, 'branch_id') and dinv.branch_id:
                        d_branch_name = dinv.branch_id.name or ''
                    # ดึงชื่อเซลล์จาก sales_contact_id
                    d_sales_name = ''
                    if hasattr(dinv, 'sales_contact_id') and dinv.sales_contact_id:
                        d_sales_name = dinv.sales_contact_id.name or ''
                    # ดึงวันเริ่มเช่า/วันคืน จาก stock.picking
                    d_rental_start = False
                    d_rental_end = False
                    if dinv.invoice_origin:
                        d_picking = self.env['stock.picking'].search([
                            ('origin', '=', dinv.invoice_origin)
                        ], limit=1, order='id desc')
                        if not d_picking:
                            d_picking = self.env['stock.picking'].search([
                                ('name', '=', dinv.invoice_origin)
                            ], limit=1)
                        if d_picking:
                            d_rental_start = d_picking.start_x_date if hasattr(d_picking, 'start_x_date') else False
                            d_rental_end = d_picking.end_x_date if hasattr(d_picking, 'end_x_date') else False
                    # คำนวณยอดเงิน
                    d_penalty_amt = getattr(dinv, 'amount_price_subtotal_without_discount', 0.0) or 0.0
                    if not d_penalty_amt:
                        d_penalty_amt = sum(
                            l.quantity * l.price_unit
                            for l in dinv.invoice_line_ids
                            if not l.exclude_from_invoice_tab
                        )
                    d_discount_amt = getattr(dinv, 'discount_amt_line', 0.0) or 0.0
                    d_discount_amt += getattr(dinv, 'discount_amt', 0.0) or 0.0
                    d_net_penalty = dinv.amount_total
                    d_amount_paid = dinv.amount_total - d_residual

                    # === สร้าง HTML table แสดงรายการสินค้า (รองรับ virtual records) ===
                    d_product_html = '<table class="table table-sm table-bordered" style="width:100%">'
                    d_product_html += '<thead><tr style="background:#f5f5f5">'
                    d_product_html += '<th>สินค้า</th><th>รายละเอียด</th>'
                    d_product_html += '<th style="text-align:right">จำนวน</th>'
                    d_product_html += '<th style="text-align:right">ราคาต่อหน่วย</th>'
                    d_product_html += '<th style="text-align:right">ส่วนลด (%)</th>'
                    d_product_html += '<th style="text-align:right">ยอดรวม</th>'
                    d_product_html += '</tr></thead><tbody>'
                    d_has_lines = False
                    for dline in dinv.invoice_line_ids:
                        if dline.exclude_from_invoice_tab:
                            continue
                        d_has_lines = True
                        d_pname = dline.product_id.name if dline.product_id else ''
                        d_product_html += '<tr>'
                        d_product_html += '<td>%s</td>' % d_pname
                        d_product_html += '<td>%s</td>' % (dline.name or '')
                        d_product_html += '<td style="text-align:right">%.2f</td>' % dline.quantity
                        d_product_html += '<td style="text-align:right">{:,.2f}</td>'.format(dline.price_unit)
                        d_product_html += '<td style="text-align:right">%.2f</td>' % dline.discount
                        d_product_html += '<td style="text-align:right">{:,.2f}</td>'.format(dline.price_subtotal)
                        d_product_html += '</tr>'
                    if not d_has_lines:
                        d_product_html += '<tr><td colspan="6" style="text-align:center;color:#999">ไม่มีรายการสินค้า</td></tr>'
                    d_product_html += '</tbody></table>'

                    damage_lines.append((0, 0, {
                        'invoice_id': dinv.id,
                        'invoice_name': dinv.name,
                        'branch_name': d_branch_name,
                        'sales_contact_name': d_sales_name,
                        'rental_start_date': d_rental_start,
                        'rental_end_date': d_rental_end,
                        'damage_amount': d_penalty_amt,
                        'discount_amount': d_discount_amt,
                        'net_damage': d_net_penalty,
                        'amount_paid': d_amount_paid,
                        'amount_residual': d_residual,
                        'product_info_html': d_product_html,
                    }))
            self.customer_damage_line_ids = damage_lines
            self.customer_damage_residual = total_damage_residual

            # === ค้นหาค่า Tax (ภาษีหัก ณ ที่จ่าย) ===
            tax_lines = [(5, 0, 0)]
            total_tax_amount = 0.0

            # === วิธีที่ 1: หาจาก paid_ids ของ payment (วิธีเดิม) ===
            paid_invoices = self.env['account.move'].search([
                ('partner_id', 'child_of', commercial.id),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('paid', 'in_payment', 'partial')),
                ('invoice_date_due', '<=', date_45_days_ago),
            ])
            _logger.info("===== [DEBUG TAX] ===== Customer: %s (commercial: %s)", self.customer_id.name, commercial.id)
            _logger.info("[DEBUG TAX] date_45_days_ago: %s", date_45_days_ago)
            _logger.info("[DEBUG TAX] paid_invoices count: %s", len(paid_invoices))
            for _dbg_inv in paid_invoices:
                _logger.info("[DEBUG TAX]   Invoice: %s | payment_state: %s | amount_total: %s | date_due: %s",
                             _dbg_inv.name, _dbg_inv.payment_state, _dbg_inv.amount_total, _dbg_inv.invoice_date_due)

            seen_tax_pairs = set()
            for tinv in paid_invoices:
                payment_inv_lines = self.env['account.payment.invoice'].search([
                    ('invoice_id', '=', tinv.id),
                    ('payment_id.state', '=', 'posted'),
                ])
                _logger.info("[DEBUG TAX] Invoice %s -> payment_inv_lines count: %s", tinv.name, len(payment_inv_lines))
                for pi_line in payment_inv_lines:
                    payment = pi_line.payment_id
                    if not payment:
                        continue
                    _logger.info("[DEBUG TAX]   Payment: %s | paid_ids count: %s | wt_cert_ids count: %s | wht_has_slip: %s",
                                 payment.name, len(payment.paid_ids), len(payment.wt_cert_ids),
                                 getattr(payment, 'wht_has_slip', 'N/A'))
                    # กรองเฉพาะ payment ที่ยังไม่ได้รับใบหัก ณ ที่จ่าย
                    if not getattr(payment, 'wht_has_slip', False):
                        _logger.info("[DEBUG TAX]   SKIP: wht_has_slip is False")
                        continue

                    # --- วิธี A: หาจาก paid_ids (payment method ชื่อ ภาษีเงินได้ถูกหัก ณ ที่จ่าย) ---
                    for paid_line in payment.paid_ids:
                        method_name = (paid_line.payment_method_id.name or '').strip() if paid_line.payment_method_id else ''
                        _logger.info("[DEBUG TAX]     paid_line method: '%s' | repr: %s | total: %s",
                                     method_name, repr(method_name), paid_line.total)
                        if method_name and 'ภาษี' in method_name and 'หัก' in method_name:
                            pair_key = (tinv.id, payment.id)
                            if pair_key in seen_tax_pairs:
                                continue
                            seen_tax_pairs.add(pair_key)
                            tax_amt = paid_line.total or 0.0
                            total_tax_amount += tax_amt
                            _logger.info("[DEBUG TAX]     >>> FOUND TAX from paid_ids: %s", tax_amt)
                            tax_lines.append((0, 0, self._prepare_tax_line_vals(tinv, payment, tax_amt)))

                    # --- วิธี B: หาจาก wt_cert_ids (withholding tax cert) ---
                    for wht_cert in payment.wt_cert_ids:
                        pair_key = (tinv.id, payment.id)
                        if pair_key in seen_tax_pairs:
                            continue
                        wht_amt = wht_cert.tax_amount or 0.0
                        if wht_amt > 0:
                            seen_tax_pairs.add(pair_key)
                            total_tax_amount += wht_amt
                            _logger.info("[DEBUG TAX]     >>> FOUND TAX from wt_cert_ids: %s (form: %s)",
                                         wht_amt, wht_cert.income_tax_form)
                            tax_lines.append((0, 0, self._prepare_tax_line_vals(tinv, payment, wht_amt)))

            # === วิธีที่ 2: หาจาก payment ที่มี wt_cert_ids โดยตรง (กรณี invoice ไม่ได้ mark เป็น paid) ===
            all_invoices_for_partner = self.env['account.move'].search([
                ('partner_id', 'child_of', commercial.id),
                ('state', '=', 'posted'),
                ('invoice_date_due', '<=', date_45_days_ago),
            ])
            _logger.info("[DEBUG TAX] === วิธี 2: all_invoices_for_partner count: %s ===", len(all_invoices_for_partner))
            for tinv2 in all_invoices_for_partner:
                payment_inv_lines2 = self.env['account.payment.invoice'].search([
                    ('invoice_id', '=', tinv2.id),
                    ('payment_id.state', '=', 'posted'),
                ])
                for pi_line2 in payment_inv_lines2:
                    payment2 = pi_line2.payment_id
                    if not payment2:
                        continue
                    # กรองเฉพาะ payment ที่ยังไม่ได้รับใบหัก ณ ที่จ่าย
                    if not getattr(payment2, 'wht_has_slip', False):
                        continue
                    # เช็คจาก wt_cert_ids
                    for wht_cert2 in payment2.wt_cert_ids:
                        pair_key2 = (tinv2.id, payment2.id)
                        if pair_key2 in seen_tax_pairs:
                            continue
                        wht_amt2 = wht_cert2.tax_amount or 0.0
                        if wht_amt2 > 0:
                            seen_tax_pairs.add(pair_key2)
                            total_tax_amount += wht_amt2
                            _logger.info("[DEBUG TAX] วิธี2 >>> FOUND TAX: invoice=%s payment=%s amt=%s",
                                         tinv2.name, payment2.name, wht_amt2)
                            tax_lines.append((0, 0, self._prepare_tax_line_vals(tinv2, payment2, wht_amt2)))
                    # เช็คจาก paid_ids
                    for paid_line2 in payment2.paid_ids:
                        method_name2 = (paid_line2.payment_method_id.name or '').strip() if paid_line2.payment_method_id else ''
                        if method_name2 and 'ภาษี' in method_name2 and 'หัก' in method_name2:
                            pair_key2 = (tinv2.id, payment2.id)
                            if pair_key2 in seen_tax_pairs:
                                continue
                            seen_tax_pairs.add(pair_key2)
                            tax_amt2 = paid_line2.total or 0.0
                            if tax_amt2 > 0:
                                total_tax_amount += tax_amt2
                                _logger.info("[DEBUG TAX] วิธี2 >>> FOUND TAX from paid_ids: invoice=%s payment=%s amt=%s",
                                             tinv2.name, payment2.name, tax_amt2)
                                tax_lines.append((0, 0, self._prepare_tax_line_vals(tinv2, payment2, tax_amt2)))

            _logger.info("[DEBUG TAX] ===== RESULT: total_tax_amount=%s, tax_lines count=%s =====",
                         total_tax_amount, len(tax_lines) - 1)
            self.customer_tax_line_ids = tax_lines
            self.customer_tax_residual = total_tax_amount

            # ดึงข้อมูลติดต่อจากลูกค้า
            self.partner_phone = self.customer_id.phone or ''
            self.partner_mobile = self.customer_id.mobile or ''
            self.partner_email = self.customer_id.email or ''
            # ดึงที่อยู่ลูกค้า
            self.partner_street = self.customer_id.street or ''
            self.partner_street2 = self.customer_id.street2 or ''
            self.partner_city = self.customer_id.city or ''
            self.partner_state_id = self.customer_id.state_id.id if self.customer_id.state_id else False
            self.partner_zip = self.customer_id.zip or ''
            self.partner_vat = self.customer_id.vat or ''
        else:
            self.customer_invoice_line_ids = [(5, 0, 0)]
            self.customer_amount_residual = 0.0
            self.customer_penalty_line_ids = [(5, 0, 0)]
            self.customer_penalty_residual = 0.0
            self.customer_damage_line_ids = [(5, 0, 0)]
            self.customer_damage_residual = 0.0
            self.customer_tax_line_ids = [(5, 0, 0)]
            self.customer_tax_residual = 0.0
            self.partner_street = ''
            self.partner_street2 = ''
            self.partner_city = ''
            self.partner_state_id = False
            self.partner_zip = ''
            self.partner_vat = ''

    def _prepare_tax_line_vals(self, invoice, payment, tax_amt):
        """สร้าง dict สำหรับ tax line record"""
        t_product_html = '<table class="table table-sm table-bordered" style="width:100%">'
        t_product_html += '<thead><tr style="background:#f5f5f5">'
        t_product_html += '<th>สินค้า</th><th>รายละเอียด</th>'
        t_product_html += '<th style="text-align:right">จำนวน</th>'
        t_product_html += '<th style="text-align:right">ราคาต่อหน่วย</th>'
        t_product_html += '<th style="text-align:right">ส่วนลด (%)</th>'
        t_product_html += '<th style="text-align:right">ยอดรวม</th>'
        t_product_html += '</tr></thead><tbody>'
        t_has_lines = False
        for tline in invoice.invoice_line_ids:
            if tline.exclude_from_invoice_tab:
                continue
            t_has_lines = True
            t_pname = tline.product_id.name if tline.product_id else ''
            t_product_html += '<tr>'
            t_product_html += '<td>%s</td>' % t_pname
            t_product_html += '<td>%s</td>' % (tline.name or '')
            t_product_html += '<td style="text-align:right">%.2f</td>' % tline.quantity
            t_product_html += '<td style="text-align:right">{:,.2f}</td>'.format(tline.price_unit)
            t_product_html += '<td style="text-align:right">%.2f</td>' % tline.discount
            t_product_html += '<td style="text-align:right">{:,.2f}</td>'.format(tline.price_subtotal)
            t_product_html += '</tr>'
        if not t_has_lines:
            t_product_html += '<tr><td colspan="6" style="text-align:center;color:#999">ไม่มีรายการสินค้า</td></tr>'
        t_product_html += '</tbody></table>'
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
            'product_info_html': t_product_html,
        }

    @api.onchange('sale_id')
    def _onchange_sale_id_clear_invoice(self):
        """เมื่อเปลี่ยนใบสั่งขาย ให้เลือกใบแจ้งหนี้อัตโนมัติ"""
        if self.sale_id:
            date_45_days_ago = date.today() - timedelta(days=45)
            # 1. หาใบแจ้งหนี้ค้างชำระที่เกินกำหนด >= 45 วัน (ทุกประเภท) จาก invoice_ids
            invoices = self.sale_id.invoice_ids.filtered(
                lambda inv: inv.state == 'posted' and
                inv.payment_state in ('not_paid', 'partial') and
                inv.invoice_date_due and inv.invoice_date_due <= date_45_days_ago)
            invoice_ids = set(invoices.ids)
            
            # 2. หาจาก invoice_origin ที่อ้างอิง SO นี้ (สำหรับ INS, etc.)
            additional_invoices = self.env['account.move'].search([
                ('invoice_origin', 'ilike', self.sale_id.name),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('not_paid', 'partial')),
                ('amount_residual', '>', 0),
                ('invoice_date_due', '<=', date_45_days_ago),
            ])
            invoice_ids.update(additional_invoices.ids)
            
            all_invoices = self.env['account.move'].browse(list(invoice_ids))
            if all_invoices:
                # เลือกใบแจ้งหนี้ใบแรกอัตโนมัติ
                self.invoice_id = all_invoices[0]
            else:
                self.invoice_id = False
        else:
            self.invoice_id = False

    @api.depends('call_log_ids')
    def _compute_call_count(self):
        for rec in self:
            rec.call_count = len(rec.call_log_ids)

    @api.depends('email_log_ids')
    def _compute_email_count(self):
        for rec in self:
            rec.email_count = len(rec.email_log_ids)

    @api.onchange('sale_id')
    def _onchange_sale_id(self):
        if self.sale_id:
            self._compute_invoice_info()
            # ดึงเบอร์โทรศัพท์ อีเมล และที่อยู่จาก partner มาใส่ให้อัตโนมัติ
            if self.sale_id.partner_id:
                p = self.sale_id.partner_id
                self.partner_phone = p.phone or ''
                self.partner_mobile = p.mobile or ''
                self.partner_email = p.email or ''
                self.partner_street = p.street or ''
                self.partner_street2 = p.street2 or ''
                self.partner_city = p.city or ''
                self.partner_state_id = p.state_id.id if p.state_id else False
                self.partner_zip = p.zip or ''
                self.partner_vat = p.vat or ''

    def action_send_email(self):
        """เปิด popup ส่งเมลติดตามหนี้"""
        self.ensure_one()
        if not self.partner_email:
            raise UserError(_('ไม่พบอีเมลของลูกค้า กรุณาเพิ่มอีเมลในข้อมูลลูกค้าก่อน'))
        
        # อัพเดทสถานะ
        if self.state == 'draft':
            self.state = 'in_progress'
        
        # คำนวณยอดค้างชำระใหม่
        self._recompute_residuals_sql()
        self.invalidate_cache()

        # สร้าง default message
        partner_name = self.partner_name or self.customer_id.name or ''
        default_subject = 'แจ้งเตือนยอดค้างชำระ - %s' % partner_name

        # === สร้างส่วนรายการค่าเช่าค้างชำระ ===
        sections = []
        grand_total = 0.0

        # 1. ค่าเช่าค้างชำระ (ใบแจ้งหนี้)
        if self.customer_amount_residual > 0:
            inv_lines = []
            for line in self.customer_invoice_line_ids:
                if line.amount_residual > 0:
                    so_name = line.invoice_origin or ''
                    inv_lines.append('- %s: {:,.2f} บาท'.format(line.amount_residual) % so_name)
            section_text = '📋 รายการค่าเช่าค้างชำระ:\n'
            section_text += '\n'.join(inv_lines)
            section_text += '\nรวมค่าเช่าค้างชำระ: {:,.2f} บาท'.format(self.customer_amount_residual)
            sections.append(section_text)
            grand_total += self.customer_amount_residual

        # 2. ค่าปรับหาย
        if self.customer_penalty_residual > 0:
            pen_lines = []
            for line in self.customer_penalty_line_ids:
                if line.amount_residual > 0:
                    pen_lines.append('- เอกสารเลขที่ %s: {:,.2f} บาท'.format(line.amount_residual) % (line.invoice_name or ''))
            section_text = '📋 รายการค่าปรับหาย:\n'
            section_text += '\n'.join(pen_lines)
            section_text += '\nรวมค่าปรับหาย: {:,.2f} บาท'.format(self.customer_penalty_residual)
            sections.append(section_text)
            grand_total += self.customer_penalty_residual

        # 3. ค่าปรับชำรุด
        if self.customer_damage_residual > 0:
            dmg_lines = []
            for line in self.customer_damage_line_ids:
                if line.amount_residual > 0:
                    dmg_lines.append('- เอกสารเลขที่ %s: {:,.2f} บาท'.format(line.amount_residual) % (line.invoice_name or ''))
            section_text = '📋 รายการค่าปรับชำรุด:\n'
            section_text += '\n'.join(dmg_lines)
            section_text += '\nรวมค่าปรับชำรุด: {:,.2f} บาท'.format(self.customer_damage_residual)
            sections.append(section_text)
            grand_total += self.customer_damage_residual

        # 4. ค่า Tax
        if self.customer_tax_residual > 0:
            tax_lines_list = []
            for line in self.customer_tax_line_ids:
                if line.tax_amount > 0:
                    tax_lines_list.append('- เอกสารเลขที่ %s: {:,.2f} บาท'.format(line.tax_amount) % (line.invoice_name or ''))
            section_text = '📋 รายการค่า Tax:\n'
            section_text += '\n'.join(tax_lines_list)
            section_text += '\nรวมค่า Tax: {:,.2f} บาท'.format(self.customer_tax_residual)
            sections.append(section_text)
            grand_total += self.customer_tax_residual

        # === สร้างสรุปยอด ===
        summary_lines = []
        if self.customer_amount_residual > 0:
            summary_lines.append('💰 ยอดค้างชำระรวมค่าเช่า: {:,.2f} บาท'.format(self.customer_amount_residual))
        if self.customer_penalty_residual > 0:
            summary_lines.append('💰 ค้างชำระค่าปรับหาย: {:,.2f} บาท'.format(self.customer_penalty_residual))
        if self.customer_damage_residual > 0:
            summary_lines.append('💰 ค้างชำระค่าปรับชำรุด: {:,.2f} บาท'.format(self.customer_damage_residual))
        if self.customer_tax_residual > 0:
            summary_lines.append('💰 ค้างชำระค่า Tax: {:,.2f} บาท'.format(self.customer_tax_residual))
        summary_text = '\n'.join(summary_lines)

        # === สร้าง sales contact info (ดึงจาก user login) ===
        sales_contact = self.env.user.name or ''
        user_partner = self.env.user.partner_id
        sales_phone = user_partner.phone or user_partner.mobile or ''
        # fallback: ดึงจาก employee
        if not sales_phone:
            employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
            if employee:
                sales_phone = employee.work_phone or employee.mobile_phone or ''
        _logger.info("[DEBUG EMAIL] sales_contact: %s | sales_phone: %s | user.partner phone: %s mobile: %s",
                     sales_contact, sales_phone, user_partner.phone, user_partner.mobile)

        # === ประกอบ email body ===
        default_body = """เรียน คุณ{partner_name}

ทางเราขอบพระคุณที่ท่านไว้วางใจใช้บริการด้วยดีเสมอมา เพื่อความถูกต้องของข้อมูลบัญชี ทางเราขอความอนุเคราะห์ท่านตรวจสอบยอดค้างชำระตามรายละเอียดดังนี้:

{sections}

{summary}

💰💰 ยอดรวม: {grand_total} บาท

หากท่านชำระเงินเรียบร้อยแล้ว ต้องขออภัยมา ณ ที่นี้ด้วยค่ะ และรบกวนท่านติดต่อแจ้งหลักฐานการชำระเงินมาที่เบอร์ 065-915-1230 เพื่อให้เราดำเนินการปรับปรุงยอดหนี้ในระบบให้ถูกต้อง

ขอขอบพระคุณสำหรับความร่วมมือค่ะ

อีเมลฉบับนี้เป็นการส่งอัตโนมัติ ไม่สามารถตอบกลับได้
หากมีข้อมูลเพิ่มเติม
ติดต่อ คุณ{sales_contact} โทร.065-915-1230""".format(
            partner_name=partner_name,
            sections='\n\n'.join(sections),
            summary=summary_text,
            grand_total='{:,.2f}'.format(grand_total),
            sales_contact=sales_contact,
            sales_phone=sales_phone,
        )
        
        # fallback: ใช้ customer_id ถ้า partner_id ว่าง
        p_id = self.partner_id.id if self.partner_id else (self.customer_id.id if self.customer_id else False)
        p_name = self.partner_name or (self.customer_id.name if self.customer_id else '')
        p_email = self.partner_email or (self.customer_id.email if self.customer_id else '')

        # === สร้าง PDF รายงานและแนบไฟล์ (ตามรูปแบบ baankhiew) ===
        attachment_ids = []

        # แนบ PDF ค่าเช่า (ถ้ามียอดค้างชำระใบแจ้งหนี้)
        if self.customer_amount_residual and self.customer_amount_residual > 0:
            try:
                report = self.env['ir.actions.report'].search([
                    ('report_name', '=', 'npd_debt_tracking_qweb.report_npd_debt_tracking_qweb')
                ], limit=1)
                if report:
                    pdf_content, content_type = report._render_qweb_pdf([self.id])
                    attachment = self.env['ir.attachment'].create({
                        'name': 'ใบแจ้งหนี้ค่าเช่า_%s.pdf' % self.name,
                        'type': 'binary',
                        'datas': base64.b64encode(pdf_content),
                        'res_model': self._name,
                        'res_id': self.id,
                        'mimetype': 'application/pdf',
                    })
                    attachment_ids.append(attachment.id)
                    _logger.info('สร้าง PDF ค่าเช่าสำเร็จ: %s' % attachment.name)
                else:
                    _logger.warning('ไม่พบ report: npd_debt_tracking_qweb.report_npd_debt_tracking_qweb')
            except Exception as e:
                _logger.warning('ไม่สามารถสร้าง PDF ค่าเช่า: %s' % str(e))

        # แนบ PDF ค่าปรับหาย (ถ้ามี)
        if self.customer_penalty_residual and self.customer_penalty_residual > 0:
            try:
                report_lost = self.env['ir.actions.report'].search([
                    ('report_name', '=', 'npd_debt_tracking_qweb.report_npd_debt_tracking_lost_qweb')
                ], limit=1)
                if report_lost:
                    pdf_content_lost, content_type = report_lost._render_qweb_pdf([self.id])
                    attachment_lost = self.env['ir.attachment'].create({
                        'name': 'ใบแจ้งหนี้ค่าปรับหาย_%s.pdf' % self.name,
                        'type': 'binary',
                        'datas': base64.b64encode(pdf_content_lost),
                        'res_model': self._name,
                        'res_id': self.id,
                        'mimetype': 'application/pdf',
                    })
                    attachment_ids.append(attachment_lost.id)
                    _logger.info('สร้าง PDF ค่าปรับหายสำเร็จ: %s' % attachment_lost.name)
                else:
                    _logger.warning('ไม่พบ report: npd_debt_tracking_qweb.report_npd_debt_tracking_lost_qweb')
            except Exception as e:
                _logger.warning('ไม่สามารถสร้าง PDF ค่าปรับหาย: %s' % str(e))

        # แนบ PDF ค่าปรับชำรุด (ถ้ามี)
        if self.customer_damage_residual and self.customer_damage_residual > 0:
            try:
                report_damage = self.env['ir.actions.report'].search([
                    ('report_name', '=', 'npd_debt_tracking_qweb.report_npd_debt_tracking_damage_qweb')
                ], limit=1)
                if report_damage:
                    pdf_content_damage, content_type = report_damage._render_qweb_pdf([self.id])
                    attachment_damage = self.env['ir.attachment'].create({
                        'name': 'ใบแจ้งหนี้ค่าปรับชำรุด_%s.pdf' % self.name,
                        'type': 'binary',
                        'datas': base64.b64encode(pdf_content_damage),
                        'res_model': self._name,
                        'res_id': self.id,
                        'mimetype': 'application/pdf',
                    })
                    attachment_ids.append(attachment_damage.id)
                    _logger.info('สร้าง PDF ค่าปรับชำรุดสำเร็จ: %s' % attachment_damage.name)
                else:
                    _logger.warning('ไม่พบ report: npd_debt_tracking_qweb.report_npd_debt_tracking_damage_qweb')
            except Exception as e:
                _logger.warning('ไม่สามารถสร้าง PDF ค่าปรับชำรุด: %s' % str(e))

        # แนบ PDF ค่า Tax (ถ้ามี)
        if self.customer_tax_residual and self.customer_tax_residual > 0:
            try:
                report_tax = self.env['ir.actions.report'].search([
                    ('report_name', '=', 'npd_debt_tracking_qweb.report_npd_debt_tracking_tax_qweb')
                ], limit=1)
                if report_tax:
                    pdf_content_tax, content_type = report_tax._render_qweb_pdf([self.id])
                    attachment_tax = self.env['ir.attachment'].create({
                        'name': 'ใบแจ้งหนี้ค่าTax_%s.pdf' % self.name,
                        'type': 'binary',
                        'datas': base64.b64encode(pdf_content_tax),
                        'res_model': self._name,
                        'res_id': self.id,
                        'mimetype': 'application/pdf',
                    })
                    attachment_ids.append(attachment_tax.id)
                    _logger.info('สร้าง PDF ค่า Tax สำเร็จ: %s' % attachment_tax.name)
                else:
                    _logger.warning('ไม่พบ report: npd_debt_tracking_qweb.report_npd_debt_tracking_tax_qweb')
            except Exception as e:
                _logger.warning('ไม่สามารถสร้าง PDF ค่า Tax: %s' % str(e))

        return {
            'name': _('📧 ส่งเมลติดตามหนี้'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.send.email.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tracking_id': self.id,
                'default_partner_id': p_id,
                'default_partner_name': p_name,
                'default_partner_email': p_email,
                'default_email_from': 'npdsgroup.official@gmail.com',
                'default_subject': default_subject,
                'default_body': default_body,
                'default_attachment_ids': [(6, 0, attachment_ids)],
            }
        }

    def action_view_email_logs(self):
        """ดูประวัติการส่งเมล"""
        self.ensure_one()
        return {
            'name': _('ประวัติการส่งเมล'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.email.log',
            'view_mode': 'tree,form',
            'domain': [('tracking_id', '=', self.id)],
        }

    def action_call_phone(self):
        """กดโทรหาลูกค้า - เปิดหน้าต่างบันทึกการโทร"""
        self.ensure_one()
        phone = self.partner_phone or self.partner_mobile
        if not phone:
            raise UserError(_('ไม่พบเบอร์โทรศัพท์ของลูกค้า'))
        if self.state == 'draft':
            self.state = 'in_progress'
        call_log = self.env['npd.debt.tracking.call.log'].create({
            'tracking_id': self.id,
            'call_date': fields.Datetime.now(),
            'phone_number': phone,
            'user_id': self.env.user.id,
        })
        return {
            'name': _('โทรหาลูกค้า'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.call.log',
            'res_id': call_log.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_tracking_id': self.id, 'default_phone_number': phone, 'form_view_initial_mode': 'edit'}
        }

    def _recompute_residuals_sql(self):
        """คำนวณยอดค้างชำระใหม่ผ่าน SQL เพื่อไม่ trigger write() ซ้ำ"""
        for rec in self:
            if not rec.id or isinstance(rec.id, models.NewId):
                continue
            inv_total = sum(l.amount_residual for l in rec.customer_invoice_line_ids)
            pen_total = sum(l.amount_residual for l in rec.customer_penalty_line_ids)
            dmg_total = sum(l.amount_residual for l in rec.customer_damage_line_ids)
            tax_total = sum(l.tax_amount for l in rec.customer_tax_line_ids)
            self.env.cr.execute("""
                UPDATE npd_debt_tracking
                SET customer_amount_residual = %s,
                    customer_penalty_residual = %s,
                    customer_damage_residual = %s,
                    customer_tax_residual = %s
                WHERE id = %s
            """, (inv_total, pen_total, dmg_total, tax_total, rec.id))
        self.invalidate_cache([
            'customer_amount_residual', 'customer_penalty_residual',
            'customer_damage_residual', 'customer_tax_residual',
        ], self.ids)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('npd.debt.tracking') or 'New'
        rec = super().create(vals)
        rec._recompute_residuals_sql()
        return rec

    def write(self, vals):
        res = super().write(vals)
        self._recompute_residuals_sql()
        return res

    def action_call_mobile(self):
        """เปิด popup โทรหาลูกค้า"""
        self.ensure_one()
        # คำนวณยอดค้างชำระใหม่ก่อนเปิด popup
        self._recompute_residuals_sql()
        phone = self.partner_phone or self.partner_mobile
        if not phone:
            raise UserError(_('ไม่พบเบอร์โทรศัพท์ของลูกค้า'))
        
        # ตรวจสอบว่า call_log_ids ยังมีอยู่จริง (ไม่ถูกลบไปแล้ว)
        existing_call_logs = self.call_log_ids.exists()
        
        # ลบ pending call logs ที่ค้างอยู่ (ไม่มีผลการโทรและไม่ได้กำลังโทร)
        pending_to_delete = existing_call_logs.filtered(lambda l: not l.is_calling and not l.call_result)
        if pending_to_delete:
            pending_to_delete.unlink()
            # รีเฟรช existing_call_logs หลังจากลบ
            existing_call_logs = self.call_log_ids.exists()
        
        active_call = existing_call_logs.filtered(lambda l: l.is_calling)
        if active_call and active_call.exists():
            return {
                'name': _('📞 กำลังโทร - %s') % self.partner_name,
                'type': 'ir.actions.act_window',
                'res_model': 'npd.debt.tracking.call.log',
                'res_id': active_call[0].id,
                'view_mode': 'form',
                'views': [(self.env.ref('npd_debt_tracking.npd_debt_tracking_call_log_calling_form').id, 'form')],
                'target': 'new',
            }
        
        clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
        if clean_phone.startswith('0'):
            clean_phone = '+66' + clean_phone[1:]
        elif not clean_phone.startswith('+'):
            clean_phone = '+66' + clean_phone
        
        if self.state == 'draft':
            self.state = 'in_progress'
        
        call_log = self.env['npd.debt.tracking.call.log'].create({
            'tracking_id': self.id,
            'call_date': fields.Datetime.now(),
            'phone_number': phone,
            'clean_phone': clean_phone,
            'user_id': self.env.user.id,
            'is_calling': False,
        })
        
        return {
            'name': _('📞 โทรหาลูกค้า - %s') % self.partner_name,
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.call.log',
            'res_id': call_log.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_debt_tracking.npd_debt_tracking_call_log_calling_form').id, 'form')],
            'target': 'new',
        }

    def action_done(self):
        """จบงานติดตามหนี้วันนี้"""
        self.ensure_one()
        empty_logs = self.call_log_ids.filtered(lambda l: not l.call_result)
        if empty_logs:
            raise UserError(_('กรุณากรอกผลการโทรให้ครบทุกรายการก่อนจบงาน\n\nยังไม่ได้กรอก %s รายการ') % len(empty_logs))
        self.state = 'done'
        return True

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancel'
        return True

    def action_reset_draft(self):
        self.ensure_one()
        self.state = 'draft'
        return True

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'name': _('ใบแจ้งหนี้ค้างชำระ'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': {'create': False},
        }

    def action_view_call_logs(self):
        self.ensure_one()
        return {
            'name': _('ประวัติการโทร'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.call.log',
            'view_mode': 'tree,form',
            'domain': [('tracking_id', '=', self.id)],
        }


class NpdDebtTrackingCallLog(models.Model):
    _name = 'npd.debt.tracking.call.log'
    _description = 'ประวัติการโทรติดตามหนี้'
    _order = 'call_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(string='ชื่อ', compute='_compute_display_name', store=True)
    
    @api.depends('partner_id', 'call_date')
    def _compute_display_name(self):
        for rec in self:
            if rec.partner_id and rec.call_date:
                rec.display_name = '%s - %s' % (rec.partner_id.name, rec.call_date.strftime('%d/%m/%Y %H:%M'))
            else:
                rec.display_name = 'New Call'

    tracking_id = fields.Many2one('npd.debt.tracking', string='รายการติดตาม', required=True, ondelete='cascade')
    call_date = fields.Datetime(string='วันเวลาที่โทร', default=fields.Datetime.now, required=True)
    phone_number = fields.Char(string='เบอร์ที่โทร')
    clean_phone = fields.Char(string='เบอร์โทร (สากล)')
    call_start_time = fields.Datetime(string='เวลาเริ่มโทร')
    call_end_time = fields.Datetime(string='เวลาจบโทร')
    is_calling = fields.Boolean(string='กำลังโทร', default=False)
    user_id = fields.Many2one('res.users', string='ผู้โทร', default=lambda self: self.env.user)
    duration = fields.Float(string='ระยะเวลา (นาที)')
    call_result = fields.Selection([
        ('answered', 'รับสาย'),
        ('no_answer', 'ไม่รับสาย'),
        ('busy', 'สายไม่ว่าง'),
        ('wrong_number', 'เบอร์ผิด'),
        ('promise_pay', 'สัญญาจะชำระ'),
        ('other', 'อื่นๆ')
    ], string='ผลการโทร')
    note = fields.Text(string='บันทึกการโทร')
    
    sale_id = fields.Many2one(related='tracking_id.sale_id', string='ใบสั่งขาย', store=True)
    partner_id = fields.Many2one(related='tracking_id.partner_id', string='ลูกค้า', store=True)
    partner_name = fields.Char(related='partner_id.name', string='ชื่อลูกค้า', store=True)
    partner_email = fields.Char(related='partner_id.email', string='อีเมล')
    partner_mobile = fields.Char(related='partner_id.mobile', string='มือถือ')
    partner_street = fields.Char(related='partner_id.street', string='ที่อยู่')
    partner_city = fields.Char(related='partner_id.city', string='เมือง')
    partner_state_id = fields.Many2one(related='partner_id.state_id', string='จังหวัด')
    amount_residual = fields.Monetary(related='tracking_id.amount_residual', string='ยอดค้างชำระ')
    currency_id = fields.Many2one(related='tracking_id.currency_id', string='สกุลเงิน')
    customer_amount_residual = fields.Monetary(related='tracking_id.customer_amount_residual', string='ยอดค้างชำระใบแจ้งหนี้')
    customer_penalty_residual = fields.Monetary(related='tracking_id.customer_penalty_residual', string='ค้างชำระค่าปรับหาย')
    customer_damage_residual = fields.Monetary(related='tracking_id.customer_damage_residual', string='ค้างชำระค่าปรับชำรุด')
    customer_tax_residual = fields.Monetary(related='tracking_id.customer_tax_residual', string='ค้างชำระค่า Tax')

    def action_dial_phone(self):
        self.ensure_one()
        phone = self.clean_phone or self.phone_number
        if not phone:
            raise UserError(_('ไม่พบเบอร์โทรศัพท์'))
        clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
        if clean_phone.startswith('0'):
            clean_phone = '+66' + clean_phone[1:]
        elif not clean_phone.startswith('+'):
            clean_phone = '+66' + clean_phone
        self.write({'clean_phone': clean_phone, 'call_start_time': fields.Datetime.now(), 'is_calling': True})
        return {'type': 'ir.actions.act_url', 'url': 'tel:%s' % clean_phone, 'target': 'self'}

    def action_dial_now(self):
        self.ensure_one()
        return self.action_dial_phone()

    def action_dial_and_start(self):
        self.ensure_one()
        phone = self.clean_phone or self.phone_number or self.partner_mobile
        if not phone:
            raise UserError(_('ไม่พบเบอร์โทรศัพท์'))
        if not self.clean_phone:
            clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
            if clean_phone.startswith('0'):
                clean_phone = '+66' + clean_phone[1:]
            elif not clean_phone.startswith('+'):
                clean_phone = '+66' + clean_phone
            self.clean_phone = clean_phone
        self.write({'call_start_time': fields.Datetime.now(), 'is_calling': True})
        return {
            'name': _('📞 กำลังโทร - %s') % self.partner_name,
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_debt_tracking.npd_debt_tracking_call_log_calling_form').id, 'form')],
            'target': 'new',
        }

    def action_start_calling(self):
        self.ensure_one()
        self.write({'call_start_time': fields.Datetime.now(), 'is_calling': True})
        return {
            'name': _('📞 กำลังโทร - %s') % self.partner_name,
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_debt_tracking.npd_debt_tracking_call_log_calling_form').id, 'form')],
            'target': 'new',
        }

    def action_start_timer(self):
        self.ensure_one()
        phone = self.clean_phone or self.phone_number or self.partner_mobile
        if phone and not self.clean_phone:
            clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
            if clean_phone.startswith('0'):
                clean_phone = '+66' + clean_phone[1:]
            elif not clean_phone.startswith('+'):
                clean_phone = '+66' + clean_phone
            self.clean_phone = clean_phone
        self.write({'call_start_time': fields.Datetime.now(), 'is_calling': True})
        return {
            'name': _('📞 กำลังโทร - %s') % self.partner_name,
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_debt_tracking.npd_debt_tracking_call_log_calling_form').id, 'form')],
            'target': 'new',
        }

    def action_make_call(self):
        self.ensure_one()
        phone = self.clean_phone or self.phone_number or self.partner_mobile
        if not phone:
            raise UserError(_('ไม่พบเบอร์โทรศัพท์'))
        if not self.clean_phone:
            clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
            if clean_phone.startswith('0'):
                clean_phone = '+66' + clean_phone[1:]
            elif not clean_phone.startswith('+'):
                clean_phone = '+66' + clean_phone
            self.clean_phone = clean_phone
        self.write({'call_start_time': fields.Datetime.now(), 'is_calling': True})
        return {
            'name': _('📞 กำลังโทร - %s') % self.partner_name,
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_debt_tracking.npd_debt_tracking_call_log_calling_form').id, 'form')],
            'target': 'new',
        }

    def action_end_call(self):
        self.ensure_one()
        now = fields.Datetime.now()
        duration = 0.0
        if self.call_start_time:
            diff = now - self.call_start_time
            duration = round(diff.total_seconds() / 60, 2)
        self.write({'call_end_time': now, 'duration': duration, 'is_calling': False})
        return {
            'name': _('📝 กรุณาบันทึกผลการโทร'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('npd_debt_tracking.npd_debt_tracking_call_log_result_form').id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'}
        }

    def action_save_and_close(self):
        self.ensure_one()
        if not self.call_result:
            raise UserError(_('⚠️ กรุณาเลือกผลการโทรก่อนบันทึก'))
        return {'type': 'ir.actions.act_window_close'}

    def js_start_call(self):
        """เริ่มโทร - เรียกจาก JavaScript"""
        try:
            # ตรวจสอบว่า record ยังมีอยู่จริง ก่อน ensure_one()
            if not self or len(self) == 0:
                return {'success': False, 'error': 'ไม่พบรายการ กรุณาปิดหน้าต่างและกดโทรใหม่'}
            self.ensure_one()
            if not self.exists():
                return {'success': False, 'error': 'รายการถูกลบไปแล้ว กรุณาปิดหน้าต่างและกดโทรใหม่'}
            phone = self.clean_phone or self.phone_number or self.partner_mobile
            if not phone:
                return {'success': False, 'error': 'ไม่พบเบอร์โทรศัพท์'}
            if not self.clean_phone:
                clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
                if clean_phone.startswith('0'):
                    clean_phone = '+66' + clean_phone[1:]
                elif not clean_phone.startswith('+'):
                    clean_phone = '+66' + clean_phone
                self.clean_phone = clean_phone
            self.write({'call_start_time': fields.Datetime.now(), 'is_calling': True})
            return {'success': True, 'phone': self.clean_phone, 'call_start_time': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        except Exception as e:
            _logger.warning('js_start_call error: %s' % str(e))
            return {'success': False, 'error': 'รายการศูนย์หายหรือถูกลบไปแล้ว กรุณาปิดหน้าต่างและกดโทรใหม่'}

    def js_end_call(self):
        """จบการโทร - เรียกจาก JavaScript"""
        try:
            # ตรวจสอบว่า record ยังมีอยู่จริง ก่อน ensure_one()
            if not self or len(self) == 0:
                return {'success': False, 'error': 'ไม่พบรายการ กรุณาปิดหน้าต่างและกดโทรใหม่'}
            self.ensure_one()
            if not self.exists():
                return {'success': False, 'error': 'รายการถูกลบไปแล้ว'}
            now = fields.Datetime.now()
            duration = 0.0
            if self.call_start_time:
                diff = now - self.call_start_time
                duration = round(diff.total_seconds() / 60, 2)
            self.write({'call_end_time': now, 'duration': duration, 'is_calling': False})
            return {
                'success': True, 'duration': duration,
                'action': {
                    'name': _('📝 กรุณาบันทึกผลการโทร'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'npd.debt.tracking.call.log',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'view_id': self.env.ref('npd_debt_tracking.npd_debt_tracking_call_log_result_form').id,
                    'target': 'new',
                    'context': {'form_view_initial_mode': 'edit'}
                }
            }
        except Exception as e:
            _logger.warning('js_end_call error: %s' % str(e))
            return {'success': False, 'error': 'รายการศูนย์หายหรือถูกลบไปแล้ว'}


class NpdDebtTrackingEmailLog(models.Model):
    _name = 'npd.debt.tracking.email.log'
    _description = 'ประวัติการส่งเมลติดตามหนี้'
    _order = 'send_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(string='ชื่อ', compute='_compute_display_name', store=True)
    
    @api.depends('partner_id', 'send_date')
    def _compute_display_name(self):
        for rec in self:
            if rec.partner_id and rec.send_date:
                rec.display_name = '%s - %s' % (rec.partner_id.name, rec.send_date.strftime('%d/%m/%Y %H:%M'))
            else:
                rec.display_name = 'New Email'

    tracking_id = fields.Many2one('npd.debt.tracking', string='รายการติดตาม', required=True, ondelete='cascade')
    send_date = fields.Datetime(string='วันเวลาที่ส่ง', default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string='ผู้ส่ง', default=lambda self: self.env.user)
    
    email_from = fields.Char(string='จากอีเมล', required=True)
    email_to = fields.Char(string='ถึงอีเมล', required=True)
    subject = fields.Char(string='หัวข้อ', required=True)
    body = fields.Text(string='เนื้อหา')
    
    attachment_ids = fields.Many2many('ir.attachment', 'email_log_attachment_rel', 'email_log_id', 
        'attachment_id', string='ไฟล์แนบ')
    attachment_count = fields.Integer(string='จำนวนไฟล์แนบ', compute='_compute_attachment_count')
    
    state = fields.Selection([
        ('draft', 'รอส่ง'),
        ('sent', 'ส่งสำเร็จ'),
        ('failed', 'ส่งไม่สำเร็จ')
    ], string='สถานะ', default='draft')
    error_message = fields.Text(string='ข้อผิดพลาด')
    
    sale_id = fields.Many2one(related='tracking_id.sale_id', string='ใบสั่งขาย', store=True)
    partner_id = fields.Many2one(related='tracking_id.partner_id', string='ลูกค้า', store=True)
    partner_name = fields.Char(related='partner_id.name', string='ชื่อลูกค้า', store=True)
    amount_residual = fields.Monetary(related='tracking_id.amount_residual', string='ยอดค้างชำระ')
    currency_id = fields.Many2one(related='tracking_id.currency_id', string='สกุลเงิน')

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)


class NpdDebtTrackingSendEmailWizard(models.TransientModel):
    _name = 'npd.debt.tracking.send.email.wizard'
    _description = 'Wizard ส่งเมลติดตามหนี้'

    # ค่า SMTP สำหรับส่งเมลโดยตรง (ไม่ผ่าน Odoo Outgoing Mail Server)
    SMTP_HOST = 'smtp.gmail.com'
    SMTP_PORT = 587
    SMTP_USER = 'npdsgroup.official@gmail.com'
    SMTP_PASS = 'unyd dkpb pclr iodq'  # App Password
    SMTP_ENCRYPTION = 'starttls'

    tracking_id = fields.Many2one('npd.debt.tracking', string='รายการติดตาม', required=True)
    partner_id = fields.Many2one('res.partner', string='ลูกค้า')
    partner_name = fields.Char(string='ชื่อลูกค้า')
    partner_email = fields.Char(string='อีเมลลูกค้า')
    
    email_from = fields.Char(string='จากอีเมล', required=True, default='npdsgroup.official@gmail.com')
    email_to = fields.Char(string='ถึงอีเมล', required=True)
    subject = fields.Char(string='หัวข้อ', required=True)
    body = fields.Text(string='เนื้อหา', required=True)
    
    attachment_ids = fields.Many2many('ir.attachment', 'wizard_attachment_rel', 'wizard_id', 
        'attachment_id', string='ไฟล์แนบ')

    @api.model
    def default_get(self, fields_list):
        res = super(NpdDebtTrackingSendEmailWizard, self).default_get(fields_list)
        if res.get('partner_email'):
            res['email_to'] = res['partner_email']
        return res

    def action_send_email(self):
        """ส่งเมลและบันทึกประวัติ - ส่งผ่าน SMTP โดยตรงจากโมดูล"""
        self.ensure_one()

        if not self.email_to:
            raise UserError(_('กรุณาระบุอีเมลผู้รับ'))

        # สร้าง Email Log ก่อน
        email_log = self.env['npd.debt.tracking.email.log'].create({
            'tracking_id': self.tracking_id.id,
            'send_date': fields.Datetime.now(),
            'user_id': self.env.user.id,
            'email_from': self.email_from,
            'email_to': self.email_to,
            'subject': self.subject,
            'body': self.body,
            'attachment_ids': [(6, 0, self.attachment_ids.ids)] if self.attachment_ids else False,
            'state': 'draft',
        })

        try:
            # ส่งเมลผ่าน SMTP โดยตรง (ใช้ค่า SMTP ที่กำหนดใน class)
            self._send_email_direct_smtp(
                email_from=self.email_from,
                email_to=self.email_to,
                subject=self.subject,
                body=self.body,
                attachments=self.attachment_ids
            )

            # ส่งสำเร็จ
            email_log.write({'state': 'sent'})
            self.tracking_id.message_post(
                body=_('📧 ส่งเมลติดตามหนี้สำเร็จ<br/>ถึง: %s<br/>หัวข้อ: %s') % (self.email_to, self.subject),
                message_type='notification'
            )
            _logger.info('Email sent successfully via direct SMTP to: %s', self.email_to)

        except Exception as e:
            error_msg = str(e)
            # แปลง error ให้เข้าใจง่าย
            if '10061' in error_msg or 'Connection refused' in error_msg:
                error_msg = (
                    'ไม่สามารถเชื่อมต่อ Mail Server ได้\n\n'
                    'กรุณาตรวจสอบ:\n'
                    '• Network Connection\n'
                    '• Firewall อนุญาต Port 587'
                )
            elif 'Authentication' in error_msg or 'auth' in error_msg.lower():
                error_msg = (
                    'การยืนยันตัวตนล้มเหลว\n\n'
                    'กรุณาติดต่อผู้ดูแลระบบเพื่อตรวจสอบ App Password'
                )
            elif 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                error_msg = (
                    'หมดเวลาในการเชื่อมต่อ Mail Server\n\n'
                    'กรุณาตรวจสอบ:\n'
                    '• Firewall อนุญาต Port 587\n'
                    '• Network Connection'
                )
            _logger.error('Error sending email via direct SMTP: %s', str(e))
            email_log.write({'state': 'failed', 'error_message': str(e)})
            raise UserError(_('เกิดข้อผิดพลาดในการส่งเมล:\n\n%s') % error_msg)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('สำเร็จ'),
                'message': _('ส่งเมลติดตามหนี้เรียบร้อยแล้ว'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _send_email_direct_smtp(self, email_from, email_to, subject, body, attachments=None):
        """ส่งเมลผ่าน SMTP โดยตรง (รูปแบบเดียวกับ baankhiew ที่ใช้งานได้)"""
        _logger.info('Sending email via direct SMTP: host=%s, port=%s, user=%s',
                     self.SMTP_HOST, self.SMTP_PORT, self.SMTP_USER)

        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = email_to
        msg['Subject'] = subject

        body_html = '<html><body><pre style="font-family: Tahoma, sans-serif;">{}</pre></body></html>'.format(
            body.replace('\n', '<br/>')
        )
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                file_data = base64.b64decode(attachment.datas) if attachment.datas else b''
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename=attachment.name or 'attachment'
                )
                msg.attach(part)

        try:
            if self.SMTP_ENCRYPTION == 'ssl':
                server = smtplib.SMTP_SSL(self.SMTP_HOST, self.SMTP_PORT, timeout=30)
            else:
                server = smtplib.SMTP(self.SMTP_HOST, self.SMTP_PORT, timeout=30)
                if self.SMTP_ENCRYPTION == 'starttls':
                    server.starttls()

            server.login(self.SMTP_USER, self.SMTP_PASS)
            server.sendmail(email_from, [email_to], msg.as_string())
            server.quit()

            _logger.info('Email sent successfully to: %s', email_to)

        except smtplib.SMTPAuthenticationError as e:
            _logger.error('SMTP Authentication Error: %s', str(e))
            raise UserError(_('การยืนยันตัวตน SMTP ล้มเหลว'))
        except smtplib.SMTPConnectError as e:
            _logger.error('SMTP Connect Error: %s', str(e))
            raise UserError(_('ไม่สามารถเชื่อมต่อ SMTP Server: %s') % str(e))
        except smtplib.SMTPException as e:
            _logger.error('SMTP Error: %s', str(e))
            raise UserError(_('เกิดข้อผิดพลาด SMTP: %s') % str(e))
        except Exception as e:
            _logger.error('General Error sending email: %s', str(e))
            raise


class NpdDebtTrackingInvoiceLine(models.Model):
    _name = 'npd.debt.tracking.invoice.line'
    _description = 'รายการใบแจ้งหนี้ค้างชำระ'
    _order = 'invoice_date_due asc'

    tracking_id = fields.Many2one('npd.debt.tracking', string='รายการติดตาม', ondelete='cascade')
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

    # HTML field สำหรับแสดงรายการสินค้า (รองรับ virtual records ใน onchange)
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)

    def action_view_invoice(self):
        """เปิดใบแจ้งหนี้เพื่อดูรายการสินค้า"""
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


class NpdDebtTrackingPenaltyLine(models.Model):
    _name = 'npd.debt.tracking.penalty.line'
    _description = 'รายการค่าปรับหาย'
    _order = 'invoice_name asc'

    tracking_id = fields.Many2one('npd.debt.tracking', string='รายการติดตาม', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขเอกสาร', related='invoice_id.name', store=True, readonly=True)
    branch_name = fields.Char(string='สาขา')
    sales_contact_name = fields.Char(string='เซลล์')
    rental_start_date = fields.Date(string='เริ่มเช่า')
    rental_end_date = fields.Date(string='วันคืน')
    penalty_amount = fields.Float(string='ค่าปรับหาย', digits=(16, 2))
    discount_amount = fields.Float(string='ส่วนลด', digits=(16, 2))
    net_penalty = fields.Float(string='ปรับหายสุทธิ', digits=(16, 2))
    amount_paid = fields.Float(string='รับชำระ', digits=(16, 2))
    amount_residual = fields.Float(string='คงเหลือ', digits=(16, 2))

    # One2many สำหรับเก็บรายการสินค้า (ใช้เมื่อ save แล้ว)
    penalty_product_line_ids = fields.One2many(
        'npd.debt.tracking.penalty.product.line',
        'penalty_line_id',
        string='รายการสินค้า'
    )

    # HTML field สำหรับแสดงรายการสินค้า (รองรับ virtual records ใน onchange)
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)

    def action_view_invoice(self):
        """เปิดใบแจ้งหนี้เพื่อดูรายการสินค้า"""
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


class NpdDebtTrackingPenaltyProductLine(models.Model):
    _name = 'npd.debt.tracking.penalty.product.line'
    _description = 'รายการสินค้าค่าปรับหาย'

    penalty_line_id = fields.Many2one('npd.debt.tracking.penalty.line', string='รายการค่าปรับหาย', ondelete='cascade')
    product_name = fields.Char(string='สินค้า')
    description = fields.Char(string='รายละเอียด')
    quantity = fields.Float(string='จำนวน', digits=(16, 2))
    price_unit = fields.Float(string='ราคาต่อหน่วย', digits=(16, 2))
    discount = fields.Float(string='ส่วนลด (%)', digits=(16, 2))
    price_subtotal = fields.Float(string='ยอดรวม', digits=(16, 2))


class NpdDebtTrackingDamageLine(models.Model):
    _name = 'npd.debt.tracking.damage.line'
    _description = 'รายการค่าปรับชำรุด'
    _order = 'invoice_name asc'

    tracking_id = fields.Many2one('npd.debt.tracking', string='รายการติดตาม', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขเอกสาร', related='invoice_id.name', store=True, readonly=True)
    branch_name = fields.Char(string='สาขา')
    sales_contact_name = fields.Char(string='เซลล์')
    rental_start_date = fields.Date(string='เริ่มเช่า')
    rental_end_date = fields.Date(string='วันคืน')
    damage_amount = fields.Float(string='ค่าปรับชำรุด', digits=(16, 2))
    discount_amount = fields.Float(string='ส่วนลด', digits=(16, 2))
    net_damage = fields.Float(string='ปรับชำรุดสุทธิ', digits=(16, 2))
    amount_paid = fields.Float(string='รับชำระ', digits=(16, 2))
    amount_residual = fields.Float(string='คงเหลือ', digits=(16, 2))

    # HTML field สำหรับแสดงรายการสินค้า (รองรับ virtual records ใน onchange)
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)

    def action_view_invoice(self):
        """เปิดใบแจ้งหนี้เพื่อดูรายการสินค้า"""
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


class NpdDebtTrackingTaxLine(models.Model):
    _name = 'npd.debt.tracking.tax.line'
    _description = 'รายการค่า Tax'
    _order = 'invoice_name asc'

    tracking_id = fields.Many2one('npd.debt.tracking', string='รายการติดตาม', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string='ใบแจ้งหนี้')
    invoice_name = fields.Char(string='เลขที่ใบแจ้งหนี้', related='invoice_id.name', store=True, readonly=True)
    invoice_origin = fields.Char(string='อ้างอิง SO')
    invoice_date = fields.Date(string='วันที่ออกใบแจ้งหนี้')
    invoice_date_due = fields.Date(string='วันกำหนดจ่าย')
    amount_total = fields.Float(string='ยอดรวมใบแจ้งหนี้', digits=(16, 2))
    payment_id = fields.Many2one('account.payment', string='รับชำระ')
    payment_name = fields.Char(string='เลขที่รับชำระ')
    tax_amount = fields.Float(string='ยอด Tax', digits=(16, 2))

    # HTML field สำหรับแสดงรายการสินค้า (รองรับ virtual records ใน onchange)
    product_info_html = fields.Html(string='รายการสินค้า', sanitize=False)

    def action_view_invoice(self):
        """เปิดใบแจ้งหนี้เพื่อดูรายการสินค้า"""
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
