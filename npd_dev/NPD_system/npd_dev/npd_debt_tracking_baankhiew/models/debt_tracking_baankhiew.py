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


class NpdDebtTrackingBaankhiew(models.Model):
    _name = 'npd.debt.tracking.baankhiew'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'ติดตามหนี้บ้านเขียว'
    _order = 'create_date desc'
    _rec_name = 'name'

    # เลขที่เอกสาร DC-YYMM-XXXX
    name = fields.Char(string='เลขที่เอกสาร', readonly=True, copy=False, 
        default='New', tracking=True)

    display_name = fields.Char(string='ชื่อ', compute='_compute_display_name', store=True)
    
    @api.depends('name', 'customer_id')
    def _compute_display_name(self):
        for rec in self:
            if rec.name and rec.name != 'New':
                if rec.customer_id:
                    rec.display_name = '%s - %s' % (rec.name, rec.customer_id.name)
                else:
                    rec.display_name = rec.name
            elif rec.customer_id:
                rec.display_name = rec.customer_id.name or 'New'
            else:
                rec.display_name = 'New'

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('npd.debt.tracking.baankhiew') or 'New'
        return super(NpdDebtTrackingBaankhiew, self).create(vals)

    def unlink(self):
        """อนุญาตให้ลบได้ทุกสถานะ"""
        # ลบ mail.message และ mail.followers ที่เกี่ยวข้องก่อน
        for rec in self:
            rec.message_ids.unlink()
        return super(NpdDebtTrackingBaankhiew, self).unlink()

    # ฟิลด์ชื่อลูกค้าที่เลือกได้อิสระ - สามารถสร้างลูกค้าใหม่ได้
    customer_id = fields.Many2one('res.partner', string='ชื่อลูกค้า',
        required=True,
        help='เลือกลูกค้าจากรายชื่อในระบบ หรือสร้างใหม่')

    # ฟิลด์เก็บรายการหนี้ค้างชำระ - ใช้ One2many เพื่อให้ลบได้และ recalculate
    debt_line_ids = fields.One2many('npd.debt.tracking.baankhiew.line', 'tracking_id',
        string='รายการหนี้ค้างชำระ')

    # ฟิลด์เก็บรายการค่าปรับชำรุด
    damage_line_ids = fields.One2many('npd.debt.tracking.baankhiew.damage.line', 'tracking_id',
        string='รายการค่าปรับชำรุด')

    # ฟิลด์เก็บรายการค่าปรับหาย
    lost_line_ids = fields.One2many('npd.debt.tracking.baankhiew.lost.line', 'tracking_id',
        string='รายการค่าปรับหาย')

    # ฟิลด์เก็บรายการค่า Tax
    tax_line_ids = fields.One2many('npd.debt.tracking.baankhiew.tax.line', 'tracking_id',
        string='รายการค่า Tax')

    partner_id = fields.Many2one(related='customer_id', string='ลูกค้า', store=True)
    partner_name = fields.Char(related='customer_id.name', string='ชื่อลูกค้า', store=True)
    partner_phone = fields.Char(related='customer_id.phone', string='เบอร์โทรศัพท์', readonly=False, store=True)
    partner_mobile = fields.Char(related='customer_id.mobile', string='มือถือ', readonly=False, store=True)
    partner_vat = fields.Char(related='customer_id.vat', string='เลขที่ผู้เสียภาษี', readonly=False, store=True)
    rental_bill_status = fields.Selection([
        ('not_closed', 'ยังไม่ปิดบิล'),
        ('closed', 'ปิดบิล'),
    ], string='สถานะบิลเช่า', tracking=True)
    partner_email = fields.Char(related='customer_id.email', string='อีเมล', readonly=False, store=True)
    partner_street = fields.Char(related='customer_id.street', string='ที่อยู่')
    partner_street2 = fields.Char(related='customer_id.street2', string='ที่อยู่ 2')
    partner_city = fields.Char(related='customer_id.city', string='เมือง')
    partner_state_id = fields.Many2one(related='customer_id.state_id', string='จังหวัด')
    partner_zip = fields.Char(related='customer_id.zip', string='รหัสไปรษณีย์')

    currency_id = fields.Many2one('res.currency', string='สกุลเงิน',
        default=lambda self: self.env.company.currency_id, store=True)
    company_id = fields.Many2one('res.company', string='บริษัท',
        default=lambda self: self.env.company, store=True)

    # ยอดรวมคำนวณจากรายการในแท็บหนี้ค้างชำระ
    amount_total = fields.Float(string='ยอดรวมทั้งหมด', compute='_compute_amounts', store=True)
    amount_residual = fields.Float(string='ยอดค้างชำระรวมค่าเช่า', compute='_compute_amounts', store=True)
    amount_rental_total = fields.Float(string='รวมค่าเช่า', compute='_compute_amounts', store=True)
    amount_rental_residual = fields.Float(string='ค้างชำระค่าเช่า', compute='_compute_amounts', store=True)
    amount_damage_total = fields.Float(string='รวมค่าปรับชำรุด', compute='_compute_amounts', store=True)
    amount_damage_residual = fields.Float(string='ค้างชำระค่าปรับชำรุด', compute='_compute_amounts', store=True)
    amount_lost_total = fields.Float(string='รวมค่าปรับหาย', compute='_compute_amounts', store=True)
    amount_lost_residual = fields.Float(string='ค้างชำระค่าปรับหาย', compute='_compute_amounts', store=True)
    amount_tax_total = fields.Float(string='รวมค่า Tax', compute='_compute_amounts', store=True)
    amount_tax_residual = fields.Float(string='ค้างชำระค่า Tax', compute='_compute_amounts', store=True)
    amount_grand_total = fields.Float(string='ยอดรวม', compute='_compute_amounts', store=True)
    debt_start_date = fields.Date(string='วันที่เริ่มเป็นหนี้', compute='_compute_debt_start_date', store=True)

    @api.depends('debt_line_ids', 'debt_line_ids.arh_date')
    def _compute_debt_start_date(self):
        """วันที่เริ่มเป็นหนี้ = วันที่เริ่มหนี้ที่น้อยที่สุดในแท็บหนี้ค้างชำระค่าเช่า"""
        for rec in self:
            arh_dates = [d for d in rec.debt_line_ids.mapped('arh_date') if d]
            rec.debt_start_date = min(arh_dates) if arh_dates else False

    @api.depends('debt_line_ids', 'debt_line_ids.total_debt', 'debt_line_ids.remaining_balance', 'debt_line_ids.total_paid',
                 'damage_line_ids', 'damage_line_ids.inv_amount', 'damage_line_ids.remaining_balance',
                 'lost_line_ids', 'lost_line_ids.net_lost',
                 'tax_line_ids', 'tax_line_ids.tax', 'tax_line_ids.remaining_balance')
    def _compute_amounts(self):
        """คำนวณยอดรวมจากรายการหนี้ค้างชำระทั้งหมด (ค่าเช่า + ค่าปรับชำรุด + ค่าปรับหาย + ค่า Tax)"""
        for rec in self:
            # ค่าเช่า
            rental_total = sum(rec.debt_line_ids.mapped('total_debt'))  # หนี้รวม
            rental_paid = sum(rec.debt_line_ids.mapped('total_paid'))  # ยอดรับชำระ
            rental_remaining = sum(rec.debt_line_ids.mapped('remaining_balance'))  # ค้างชำระสุทธิ
            # ค่าปรับชำรุด
            damage_total = sum(rec.damage_line_ids.mapped('inv_amount'))
            damage_residual = sum(rec.damage_line_ids.mapped('remaining_balance'))
            # ค่าปรับหาย - ดึงจาก net_lost (ปรับหายสุทธิ)
            lost_total = sum(rec.lost_line_ids.mapped('net_lost'))
            lost_residual = sum(rec.lost_line_ids.mapped('net_lost'))  # ค้างชำระค่าปรับหาย = net_lost
            # ค่า Tax
            tax_total = sum(rec.tax_line_ids.mapped('tax'))
            tax_residual = sum(rec.tax_line_ids.mapped('remaining_balance'))
            
            rec.amount_rental_total = rental_total
            rec.amount_rental_residual = rental_total  # ค้างชำระค่าเช่า = ยอดรวม (total_debt)
            rec.amount_damage_total = damage_total
            rec.amount_damage_residual = damage_residual
            rec.amount_lost_total = lost_total
            rec.amount_lost_residual = lost_residual  # ดึงจาก net_lost
            rec.amount_tax_total = tax_total
            rec.amount_tax_residual = tax_residual
            rec.amount_total = rental_total + damage_total + lost_total + tax_total
            rec.amount_residual = rental_remaining  # ยอดค้างชำระรวมค่าเช่า = remaining_balance (ค้างชำระสุทธิ)
            # ยอดรวม = ยอดค้างชำระรวมค่าเช่า + ค้างชำระค่าปรับชำรุด + ค้างชำระค่าปรับหาย + ค้างชำระค่า Tax
            rec.amount_grand_total = rental_remaining + damage_residual + lost_residual + tax_residual

    state = fields.Selection([
        ('draft', 'รอดำเนินการ'),
        ('in_progress', 'กำลังติดตาม'),
        ('done', 'เสร็จสิ้น'),
        ('cancel', 'ยกเลิก')
    ], string='สถานะ', default='draft', tracking=True)
    
    tracking_date = fields.Date(string='วันที่ติดตาม', default=fields.Date.today)
    note = fields.Text(string='หมายเหตุ')
    
    call_log_ids = fields.One2many('npd.debt.tracking.baankhiew.call.log', 'tracking_id', string='ประวัติการโทร')
    call_count = fields.Integer(string='จำนวนครั้งที่โทร', compute='_compute_call_count')
    
    # Email Log
    email_log_ids = fields.One2many('npd.debt.tracking.baankhiew.email.log', 'tracking_id', string='ประวัติการส่งเมล')
    email_count = fields.Integer(string='จำนวนครั้งที่ส่งเมล', compute='_compute_email_count')

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        """เมื่อเปลี่ยนลูกค้า ให้ล้างข้อมูลเดิม (ต้องกดปุ่มดึงข้อมูลเอง)"""
        # ไม่ต้องทำอะไร - ให้ user กดปุ่มดึงข้อมูลเอง
        pass

    def _fetch_all_data(self):
        """ดึงข้อมูลทั้งค่าเช่าและค่าปรับชำรุด"""
        if not self.customer_id:
            return

        # ใช้ partner_vat (เลขประจำตัวผู้เสียภาษี) ในการค้นหา
        partner_vat = self.partner_vat
        if not partner_vat:
            return

        warnings = []
        
        # ดึงข้อมูลค่าเช่า
        BaankhiewInvoice = self.env['npd.debt.tracking.baankhiew.invoice']
        invoice_ids = BaankhiewInvoice.fetch_invoices_by_customer(partner_vat)

        if invoice_ids:
            invoices = BaankhiewInvoice.browse(invoice_ids)

            if invoices:
                line_vals = []
                for inv in invoices:
                    line_vals.append((0, 0, {
                        'invoice_id': inv.id,
                    }))
                self.debt_line_ids = line_vals

        # ดึงข้อมูลค่าปรับชำรุด
        DamageInvoice = self.env['npd.debt.tracking.baankhiew.damage.invoice']
        damage_ids = DamageInvoice.fetch_damage_invoices_by_customer(partner_vat)
        
        if damage_ids:
            damage_invoices = DamageInvoice.browse(damage_ids).filtered(
                lambda inv: inv.remaining_balance > 0
            )
            
            if damage_invoices:
                line_vals = []
                for inv in damage_invoices:
                    line_vals.append((0, 0, {
                        'damage_invoice_id': inv.id,
                    }))
                self.damage_line_ids = line_vals
        
        # แจ้งเตือนถ้าไม่พบข้อมูลทั้ง 2 ประเภท
        if not invoice_ids and not damage_ids:
            return {
                'warning': {
                    'title': 'ไม่พบข้อมูลในบ้านเขียว',
                    'message': 'ไม่พบข้อมูลใบแจ้งหนี้ของเลขประจำตัวผู้เสียภาษี "%s" ในระบบบ้านเขียว' % partner_vat
                }
            }

    def action_fetch_baankhiew_invoices(self):
        """ปุ่มดึงข้อมูลใบแจ้งหนี้จากบ้านเขียว (ค่าเช่า, ค่าปรับชำรุด และค่าปรับหาย)"""
        self.ensure_one()
        if not self.customer_id:
            raise UserError(_('กรุณาเลือกลูกค้าก่อน'))

        # ใช้ partner_vat (เลขประจำตัวผู้เสียภาษี) ในการค้นหา
        partner_vat = self.partner_vat
        if not partner_vat:
            raise UserError(_('กรุณาระบุเลขประจำตัวผู้เสียภาษีของลูกค้าก่อน'))
        
        messages = []
        
        # ดึงข้อมูลค่าเช่า
        BaankhiewInvoice = self.env['npd.debt.tracking.baankhiew.invoice']
        invoice_ids = BaankhiewInvoice.fetch_invoices_by_customer(partner_vat)

        debt_line_vals = []
        if invoice_ids:
            invoices = BaankhiewInvoice.browse(invoice_ids)

            if invoices:
                for inv in invoices:
                    debt_line_vals.append((0, 0, {
                        'invoice_id': inv.id,
                    }))
                messages.append(_('ค่าเช่า: พบ %d รายการ') % len(invoices))
            else:
                messages.append(_('ค่าเช่า: ไม่มีรายการ'))
        else:
            messages.append(_('ค่าเช่า: ไม่พบข้อมูล'))

        # ดึงข้อมูลค่าปรับชำรุด
        DamageInvoice = self.env['npd.debt.tracking.baankhiew.damage.invoice']
        damage_ids = DamageInvoice.fetch_damage_invoices_by_customer(partner_vat)

        damage_line_vals = []
        if damage_ids:
            damage_invoices = DamageInvoice.browse(damage_ids).filtered(
                lambda inv: inv.remaining_balance > 0
            )

            if damage_invoices:
                for inv in damage_invoices:
                    damage_line_vals.append((0, 0, {
                        'damage_invoice_id': inv.id,
                    }))
                messages.append(_('ค่าปรับชำรุด: พบ %d รายการ') % len(damage_invoices))
            else:
                messages.append(_('ค่าปรับชำรุด: ไม่มีรายการค้างชำระ'))
        else:
            messages.append(_('ค่าปรับชำรุด: ไม่พบข้อมูล'))

        # ดึงข้อมูลค่าปรับหาย
        LostInvoice = self.env['npd.debt.tracking.baankhiew.lost.invoice']
        lost_ids = LostInvoice.fetch_lost_invoices_by_customer(partner_vat)

        lost_line_vals = []
        if lost_ids:
            lost_invoices = LostInvoice.browse(lost_ids).filtered(
                lambda inv: inv.remaining_balance > 0
            )

            if lost_invoices:
                for inv in lost_invoices:
                    lost_line_vals.append((0, 0, {
                        'lost_invoice_id': inv.id,
                    }))
                messages.append(_('ค่าปรับหาย: พบ %d รายการ') % len(lost_invoices))
            else:
                messages.append(_('ค่าปรับหาย: ไม่มีรายการค้างชำระ'))
        else:
            messages.append(_('ค่าปรับหาย: ไม่พบข้อมูล'))

        # ดึงข้อมูลค่า Tax
        TaxInvoice = self.env['npd.debt.tracking.baankhiew.tax.invoice']
        tax_ids = TaxInvoice.fetch_tax_invoices_by_customer(partner_vat)

        tax_line_vals = []
        if tax_ids:
            tax_invoices = TaxInvoice.browse(tax_ids).filtered(
                lambda inv: inv.remaining_balance > 0
            )

            if tax_invoices:
                for inv in tax_invoices:
                    tax_line_vals.append((0, 0, {
                        'tax_invoice_id': inv.id,
                    }))
                messages.append(_('ค่า Tax: พบ %d รายการ') % len(tax_invoices))
            else:
                messages.append(_('ค่า Tax: ไม่มีรายการค้างชำระ'))
        else:
            messages.append(_('ค่า Tax: ไม่พบข้อมูล'))

        # บันทึกข้อมูลลง database (ใช้ write เพื่อบันทึกทันที)
        update_vals = {
            'debt_line_ids': [(5, 0, 0)] + debt_line_vals,
            'damage_line_ids': [(5, 0, 0)] + damage_line_vals,
            'lost_line_ids': [(5, 0, 0)] + lost_line_vals,
            'tax_line_ids': [(5, 0, 0)] + tax_line_vals,
        }
        self.write(update_vals)

        # อัพเดทสถานะบิลเช่า
        self._update_rental_bill_status()

        # กำหนดประเภทข้อความ
        has_data = bool(debt_line_vals or damage_line_vals or lost_line_vals or tax_line_vals)
        msg_type = 'success' if has_data else 'warning'
        
        # Reload form เพื่อแสดงข้อมูลใหม่
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.baankhiew',
            'res_id': self.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }

    def _update_rental_bill_status(self):
        """อัพเดทสถานะบิลเช่าจากรายการหนี้ค้างชำระ"""
        self.ensure_one()
        if not self.debt_line_ids:
            self.rental_bill_status = False
            return
        
        # ตรวจสอบว่ามีรายการไหนที่สถานะเป็น "ยังไม่ปิดบิล"
        has_not_closed = any(
            line.bill_status == 'ยังไม่ปิดบิล' 
            for line in self.debt_line_ids
        )
        
        if has_not_closed:
            self.rental_bill_status = 'not_closed'
        else:
            self.rental_bill_status = 'closed'

    def action_test_baankhiew_connection(self):
        """ปุ่มทดสอบการเชื่อมต่อกับบ้านเขียว"""
        self.ensure_one()
        BaankhiewInvoice = self.env['npd.debt.tracking.baankhiew.invoice']
        return BaankhiewInvoice.action_test_connection()

    @api.depends('call_log_ids')
    def _compute_call_count(self):
        for rec in self:
            rec.call_count = len(rec.call_log_ids)

    @api.depends('email_log_ids')
    def _compute_email_count(self):
        for rec in self:
            rec.email_count = len(rec.email_log_ids)

    def action_send_email(self):
        """เปิด popup ส่งเมลติดตามหนี้ พร้อมแนบ PDF รายงาน"""
        self.ensure_one()
        if not self.partner_email:
            raise UserError(_('ไม่พบอีเมลของลูกค้า กรุณาเพิ่มอีเมลในข้อมูลลูกค้าก่อน'))
        
        if self.state == 'draft':
            self.state = 'in_progress'
        
        # สร้างรายละเอียดค่าเช่าค้างชำระ
        debt_details = ''
        if self.debt_line_ids:
            debt_details += '📋 รายการค่าเช่าค้างชำระ:\n'
            for line in self.debt_line_ids:
                debt_details += '   - %s: %s บาท\n' % (line.invoice_number or 'N/A', '{:,.2f}'.format(line.remaining_balance))
            rental_total = sum(self.debt_line_ids.mapped('remaining_balance'))
            debt_details += '   รวมค่าเช่าค้างชำระ: %s บาท\n' % '{:,.2f}'.format(rental_total)
        
        # สร้างรายละเอียดค่าปรับชำรุด (ถ้ามี)
        damage_details = ''
        if self.damage_line_ids:
            damage_details += '\n📋 รายการค่าปรับชำรุด:\n'
            for line in self.damage_line_ids:
                damage_details += '   - เอกสารเลขที่ %s: %s บาท\n' % (line.inv_no or 'N/A', '{:,.2f}'.format(line.remaining_balance))
            damage_total = sum(self.damage_line_ids.mapped('remaining_balance'))
            damage_details += '   รวมค่าปรับชำรุด: %s บาท\n' % '{:,.2f}'.format(damage_total)
        
        # สร้างรายละเอียดค่าปรับหาย (ถ้ามี)
        lost_details = ''
        if self.lost_line_ids:
            lost_details += '\n📋 รายการค่าปรับหาย:\n'
            for line in self.lost_line_ids:
                lost_details += '   - เอกสารเลขที่ %s: %s บาท\n' % (line.doc_id or 'N/A', '{:,.2f}'.format(line.net_lost))
            lost_total = sum(self.lost_line_ids.mapped('net_lost'))
            lost_details += '   รวมค่าปรับหาย: %s บาท\n' % '{:,.2f}'.format(lost_total)
        
        # สร้างรายละเอียดค่า Tax (ถ้ามี)
        tax_details = ''
        if self.tax_line_ids:
            tax_details += '\n📋 รายการค่า Tax:\n'
            for line in self.tax_line_ids:
                tax_details += '   - เอกสารเลขที่ %s: %s บาท\n' % (line.invoice_number or 'N/A', '{:,.2f}'.format(line.tax))
            tax_total = sum(self.tax_line_ids.mapped('tax'))
            tax_details += '   รวมค่า Tax: %s บาท\n' % '{:,.2f}'.format(tax_total)
        
        default_subject = 'แจ้งเตือนยอดค้างชำระ - %s' % self.partner_name
        # ดึงชื่อผู้ใช้จากการ login
        login_user_name = self.env.user.name or 'เจ้าหน้าที่'
        
        default_body = """เรียน คุณ%s

ทางเราขอขอบพระคุณที่ท่านไว้วางใจใช้บริการด้วยดีเสมอมา เพื่อความถูกต้องของข้อมูลบัญชี ทางเราขอความอนุเคราะห์ท่านตรวจสอบยอดค้างชำระตามรายละเอียดดังนี้:

%s%s%s%s
══════════════════════════════════
💰 ยอดค้างชำระรวมค่าเช่า: %s บาท
💰 ค้างชำระค่าปรับชำรุด: %s บาท
💰 ค้างชำระค่าปรับหาย: %s บาท
💰 ค้างชำระค่า Tax: %s บาท
══════════════════════════════════
💰💰 ยอดรวม: %s บาท
══════════════════════════════════

หากท่านชำระเงินเรียบร้อยแล้ว ต้องขออภัยมา ณ ที่นี้ด้วยครับ/ค่ะ และรบกวนท่านติดต่อแจ้งหลักฐานการชำระเงินมาที่เบอร์ 065-915-1230 เพื่อให้เราดำเนินการปรับปรุงยอดหนี้ในระบบให้ถูกต้อง

ขอขอบพระคุณสำหรับความร่วมมือครับ/ค่ะ

อีเมลฉบับนี้เป็นการส่งอัตโนมัติ ไม่สามารถตอบกลับได้
หากมีข้อมูลเพิ่มเติม
ติดต่อ คุณ%s โทร.065-915-1230""" % (
            self.partner_name or '',
            debt_details,
            damage_details,
            lost_details,
            tax_details,
            '{:,.2f}'.format(self.amount_residual),
            '{:,.2f}'.format(self.amount_damage_residual),
            '{:,.2f}'.format(self.amount_lost_residual),
            '{:,.2f}'.format(self.amount_tax_residual),
            '{:,.2f}'.format(self.amount_grand_total),
            login_user_name
        )
        
        # สร้าง PDF รายงานและแนบไฟล์
        attachment_ids = []
        
        # แนบ PDF ค่าเช่า (ถ้ามี debt_line_ids)
        if self.debt_line_ids:
            try:
                report = self.env['ir.actions.report'].search([
                    ('report_name', '=', 'npd_debt_tracking_baankhiew_qweb.report_npd_debt_tracking_baankhiew_qweb')
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
                    _logger.warning('ไม่พบ report: npd_debt_tracking_baankhiew_qweb')
            except Exception as e:
                _logger.warning('ไม่สามารถสร้าง PDF ค่าเช่า: %s' % str(e))
        
        # แนบ PDF ค่าปรับชำรุด (ถ้ามี damage_line_ids)
        if self.damage_line_ids:
            try:
                report_damage = self.env['ir.actions.report'].search([
                    ('report_name', '=', 'npd_debt_tracking_baankhiew_qweb.report_npd_debt_tracking_baankhiew_damage_qweb')
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
                    _logger.warning('ไม่พบ report: npd_debt_tracking_baankhiew_damage_qweb')
            except Exception as e:
                _logger.warning('ไม่สามารถสร้าง PDF ค่าปรับชำรุด: %s' % str(e))
        
        # แนบ PDF ค่าปรับหาย (ถ้ามี lost_line_ids)
        if self.lost_line_ids:
            try:
                report_lost = self.env['ir.actions.report'].search([
                    ('report_name', '=', 'npd_debt_tracking_baankhiew_qweb.report_npd_debt_tracking_baankhiew_lost_qweb')
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
                    _logger.warning('ไม่พบ report: npd_debt_tracking_baankhiew_lost_qweb')
            except Exception as e:
                _logger.warning('ไม่สามารถสร้าง PDF ค่าปรับหาย: %s' % str(e))
        
        # แนบ PDF ค่า Tax (ถ้ามี tax_line_ids)
        if self.tax_line_ids:
            try:
                report_tax = self.env['ir.actions.report'].search([
                    ('report_name', '=', 'npd_debt_tracking_baankhiew_qweb.report_npd_debt_tracking_baankhiew_tax_qweb')
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
                    _logger.warning('ไม่พบ report: npd_debt_tracking_baankhiew_tax_qweb')
            except Exception as e:
                _logger.warning('ไม่สามารถสร้าง PDF ค่า Tax: %s' % str(e))
        
        return {
            'name': _('📧 ส่งเมลติดตามหนี้'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.baankhiew.send.email.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tracking_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_partner_name': self.partner_name,
                'default_partner_email': self.partner_email,
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
            'res_model': 'npd.debt.tracking.baankhiew.email.log',
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
        call_log = self.env['npd.debt.tracking.baankhiew.call.log'].create({
            'tracking_id': self.id,
            'call_date': fields.Datetime.now(),
            'phone_number': phone,
            'user_id': self.env.user.id,
        })
        return {
            'name': _('โทรหาลูกค้า'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.baankhiew.call.log',
            'res_id': call_log.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_tracking_id': self.id, 'default_phone_number': phone, 'form_view_initial_mode': 'edit'}
        }

    def action_call_mobile(self):
        """เปิด popup โทรหาลูกค้า"""
        self.ensure_one()
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
                'res_model': 'npd.debt.tracking.baankhiew.call.log',
                'res_id': active_call[0].id,
                'view_mode': 'form',
                'views': [(self.env.ref('npd_debt_tracking_baankhiew.npd_debt_tracking_baankhiew_call_log_calling_form').id, 'form')],
                'target': 'new',
            }
        
        clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
        if clean_phone.startswith('0'):
            clean_phone = '+66' + clean_phone[1:]
        elif not clean_phone.startswith('+'):
            clean_phone = '+66' + clean_phone
        
        if self.state == 'draft':
            self.state = 'in_progress'
        
        call_log = self.env['npd.debt.tracking.baankhiew.call.log'].create({
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
            'res_model': 'npd.debt.tracking.baankhiew.call.log',
            'res_id': call_log.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_debt_tracking_baankhiew.npd_debt_tracking_baankhiew_call_log_calling_form').id, 'form')],
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

    def action_view_call_logs(self):
        self.ensure_one()
        return {
            'name': _('ประวัติการโทร'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.baankhiew.call.log',
            'view_mode': 'tree,form',
            'domain': [('tracking_id', '=', self.id)],
        }


class NpdDebtTrackingBaankhiewLine(models.Model):
    """รายการหนี้ค้างชำระ - แท็บหนี้ค้างชำระ"""
    _name = 'npd.debt.tracking.baankhiew.line'
    _description = 'รายการหนี้ค้างชำระ'
    _order = 'invoice_number'

    tracking_id = fields.Many2one('npd.debt.tracking.baankhiew', string='รายการติดตาม', 
        required=True, ondelete='cascade')
    invoice_id = fields.Many2one('npd.debt.tracking.baankhiew.invoice', string='ใบแจ้งหนี้',
        required=True, ondelete='cascade')

    # Related fields จาก invoice
    invoice_number = fields.Char(related='invoice_id.invoice_number', string='เลขที่ใบกำกับเช่า', store=True)
    branch_name = fields.Char(related='invoice_id.branch_name', string='สาขา', store=True)
    total_debt = fields.Float(related='invoice_id.total_debt', string='ยอดรวม', store=True)
    total_paid = fields.Float(related='invoice_id.total_paid', string='รับชำระ', store=True)
    remaining_balance = fields.Float(related='invoice_id.remaining_balance', string='ค้างชำระสุทธิ', store=True)
    arh_date = fields.Date(related='invoice_id.arh_date', string='วันที่เริ่มหนี้', store=True)
    due_date = fields.Date(related='invoice_id.due_date', string='วันครบกำหนด', store=True)
    debt_duration = fields.Integer(related='invoice_id.debt_duration', string='จำนวนวัน', store=True)
    responsible_party = fields.Char(related='invoice_id.responsible_party', string='ผู้รับผิดชอบ', store=True)
    bill_status = fields.Char(related='invoice_id.bill_status', string='สถานะบิล', store=True)


class NpdDebtTrackingBaankhiewDamageLine(models.Model):
    """รายการค่าปรับชำรุด - แท็บค่าปรับชำรุด"""
    _name = 'npd.debt.tracking.baankhiew.damage.line'
    _description = 'รายการค่าปรับชำรุด'
    _order = 'inv_no'

    tracking_id = fields.Many2one('npd.debt.tracking.baankhiew', string='รายการติดตาม', 
        required=True, ondelete='cascade')
    damage_invoice_id = fields.Many2one('npd.debt.tracking.baankhiew.damage.invoice', string='ใบแจ้งหนี้ค่าปรับ',
        required=True, ondelete='cascade')

    # Related fields จาก damage invoice
    inv_no = fields.Char(related='damage_invoice_id.inv_no', string='เลขเอกสาร', store=True)
    branch_name = fields.Char(related='damage_invoice_id.branch_name', string='สาขา', store=True)
    inv_amount = fields.Float(related='damage_invoice_id.inv_amount', string='ค่าปรับชำรุด', store=True)
    total_paid = fields.Float(related='damage_invoice_id.total_paid', string='รับชำระ', store=True)
    remaining_balance = fields.Float(related='damage_invoice_id.remaining_balance', string='คงเหลือ', store=True)
    dateissue = fields.Date(related='damage_invoice_id.dateissue', string='วันที่', store=True)
    inv_cusname = fields.Char(related='damage_invoice_id.inv_cusname', string='ชื่อลูกค้า', store=True)
    cus_cpnname = fields.Char(related='damage_invoice_id.cus_cpnname', string='บริษัท', store=True)


class NpdDebtTrackingBaankhiewCallLog(models.Model):
    _name = 'npd.debt.tracking.baankhiew.call.log'
    _description = 'ประวัติการโทรติดตามหนี้บ้านเขียว'
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

    tracking_id = fields.Many2one('npd.debt.tracking.baankhiew', string='รายการติดตาม', required=True, ondelete='cascade')
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

    partner_id = fields.Many2one(related='tracking_id.partner_id', string='ลูกค้า', store=True)
    partner_name = fields.Char(related='partner_id.name', string='ชื่อลูกค้า', store=True)
    partner_email = fields.Char(related='partner_id.email', string='อีเมล')
    partner_mobile = fields.Char(related='partner_id.mobile', string='มือถือ')
    partner_street = fields.Char(related='partner_id.street', string='ที่อยู่')
    partner_city = fields.Char(related='partner_id.city', string='เมือง')
    partner_state_id = fields.Many2one(related='partner_id.state_id', string='จังหวัด')
    # ยอดค้างชำระแยกประเภท
    amount_rental_residual = fields.Float(related='tracking_id.amount_rental_residual', string='ค้างชำระค่าเช่า')
    amount_residual = fields.Float(related='tracking_id.amount_residual', string='ยอดค้างชำระรวมค่าเช่า')
    amount_damage_residual = fields.Float(related='tracking_id.amount_damage_residual', string='ค้างชำระค่าปรับชำรุด')
    amount_lost_residual = fields.Float(related='tracking_id.amount_lost_residual', string='ค้างชำระค่าปรับหาย')
    amount_tax_residual = fields.Float(related='tracking_id.amount_tax_residual', string='ค้างชำระค่า Tax')
    amount_grand_total = fields.Float(related='tracking_id.amount_grand_total', string='ยอดรวม')
    currency_id = fields.Many2one(related='tracking_id.currency_id', string='สกุลเงิน')

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
            'res_model': 'npd.debt.tracking.baankhiew.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_debt_tracking_baankhiew.npd_debt_tracking_baankhiew_call_log_calling_form').id, 'form')],
            'target': 'new',
        }

    def action_start_calling(self):
        self.ensure_one()
        self.write({'call_start_time': fields.Datetime.now(), 'is_calling': True})
        return {
            'name': _('📞 กำลังโทร - %s') % self.partner_name,
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.baankhiew.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_debt_tracking_baankhiew.npd_debt_tracking_baankhiew_call_log_calling_form').id, 'form')],
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
            'res_model': 'npd.debt.tracking.baankhiew.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_debt_tracking_baankhiew.npd_debt_tracking_baankhiew_call_log_calling_form').id, 'form')],
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
            'res_model': 'npd.debt.tracking.baankhiew.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_debt_tracking_baankhiew.npd_debt_tracking_baankhiew_call_log_calling_form').id, 'form')],
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
            'res_model': 'npd.debt.tracking.baankhiew.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('npd_debt_tracking_baankhiew.npd_debt_tracking_baankhiew_call_log_result_form').id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'}
        }

    def action_save_and_close(self):
        self.ensure_one()
        if not self.call_result:
            raise UserError(_('⚠️ กรุณาเลือกผลการโทรก่อนบันทึก'))
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel_call(self):
        """ยกเลิกการโทรและลบ record ถ้าไม่มีผลการโทร"""
        self.ensure_one()
        # ตรวจสอบว่า record ยังมีอยู่ก่อนลบ
        if self.exists() and not self.call_result:
            self.unlink()
        return {'type': 'ir.actions.act_window_close'}

    def js_start_call(self):
        """เริ่มโทร - เรียกจาก JavaScript"""
        try:
            # ตรวจสอบว่า recordset มีข้อมูลหรือไม่
            if not self or len(self) == 0:
                return {'success': False, 'error': 'ไม่พบรายการ กรุณาปิดหน้าต่างและกดโทรใหม่'}
            self.ensure_one()
            # ตรวจสอบว่า record ยังมีอยู่หรือไม่
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
            # ตรวจสอบว่า recordset มีข้อมูลหรือไม่
            if not self or len(self) == 0:
                return {'success': False, 'error': 'ไม่พบรายการ กรุณาปิดหน้าต่างและกดโทรใหม่'}
            self.ensure_one()
            # ตรวจสอบว่า record ยังมีอยู่หรือไม่
            if not self.exists():
                return {'success': False, 'error': 'รายการถูกลบไปแล้ว กรุณารีเฟรชหน้าจอ'}
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
                    'res_model': 'npd.debt.tracking.baankhiew.call.log',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'view_id': self.env.ref('npd_debt_tracking_baankhiew.npd_debt_tracking_baankhiew_call_log_result_form').id,
                    'target': 'new',
                    'context': {'form_view_initial_mode': 'edit'}
                }
            }
        except Exception as e:
            _logger.warning('js_end_call error: %s' % str(e))
            return {'success': False, 'error': 'รายการศูนย์หายหรือถูกลบไปแล้ว'}


class NpdDebtTrackingBaankhiewEmailLog(models.Model):
    _name = 'npd.debt.tracking.baankhiew.email.log'
    _description = 'ประวัติการส่งเมลติดตามหนี้บ้านเขียว'
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

    tracking_id = fields.Many2one('npd.debt.tracking.baankhiew', string='รายการติดตาม', required=True, ondelete='cascade')
    send_date = fields.Datetime(string='วันเวลาที่ส่ง', default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string='ผู้ส่ง', default=lambda self: self.env.user)
    
    email_from = fields.Char(string='จากอีเมล', required=True)
    email_to = fields.Char(string='ถึงอีเมล', required=True)
    subject = fields.Char(string='หัวข้อ', required=True)
    body = fields.Text(string='เนื้อหา')
    
    attachment_ids = fields.Many2many('ir.attachment', 'email_log_baankhiew_attachment_rel', 'email_log_id', 
        'attachment_id', string='ไฟล์แนบ')
    attachment_count = fields.Integer(string='จำนวนไฟล์แนบ', compute='_compute_attachment_count')
    
    state = fields.Selection([
        ('draft', 'รอส่ง'),
        ('sent', 'ส่งสำเร็จ'),
        ('failed', 'ส่งไม่สำเร็จ')
    ], string='สถานะ', default='draft')
    error_message = fields.Text(string='ข้อผิดพลาด')
    
    partner_id = fields.Many2one(related='tracking_id.partner_id', string='ลูกค้า', store=True)
    partner_name = fields.Char(related='partner_id.name', string='ชื่อลูกค้า', store=True)
    amount_residual = fields.Float(related='tracking_id.amount_residual', string='ยอดค้างชำระ')
    currency_id = fields.Many2one(related='tracking_id.currency_id', string='สกุลเงิน')

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)


class NpdDebtTrackingBaankhiewSendEmailWizard(models.TransientModel):
    _name = 'npd.debt.tracking.baankhiew.send.email.wizard'
    _description = 'Wizard ส่งเมลติดตามหนี้บ้านเขียว'

    tracking_id = fields.Many2one('npd.debt.tracking.baankhiew', string='รายการติดตาม', required=True)
    partner_id = fields.Many2one('res.partner', string='ลูกค้า')
    partner_name = fields.Char(string='ชื่อลูกค้า')
    partner_email = fields.Char(string='อีเมลลูกค้า')
    
    email_from = fields.Char(string='จากอีเมล', required=True, default='npdsgroup.official@gmail.com')
    email_to = fields.Char(string='ถึงอีเมล', required=True)
    subject = fields.Char(string='หัวข้อ', required=True)
    body = fields.Text(string='เนื้อหา', required=True)
    
    attachment_ids = fields.Many2many('ir.attachment', 'wizard_baankhiew_attachment_rel', 'wizard_id', 
        'attachment_id', string='ไฟล์แนบ')

    @api.model
    def default_get(self, fields_list):
        res = super(NpdDebtTrackingBaankhiewSendEmailWizard, self).default_get(fields_list)
        if res.get('partner_email'):
            res['email_to'] = res['partner_email']
        return res

    # ค่า SMTP สำหรับส่งเมลโดยตรง
    SMTP_HOST = 'smtp.gmail.com'
    SMTP_PORT = 587
    SMTP_USER = 'npdsgroup.official@gmail.com'
    SMTP_PASS = 'unyd dkpb pclr iodq'
    SMTP_ENCRYPTION = 'starttls'

    def action_send_email(self):
        """ส่งเมลและบันทึกประวัติ"""
        self.ensure_one()

        if not self.email_to:
            raise UserError(_('กรุณาระบุอีเมลผู้รับ'))

        email_log = self.env['npd.debt.tracking.baankhiew.email.log'].create({
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
            self._send_email_direct_smtp(
                email_from=self.email_from,
                email_to=self.email_to,
                subject=self.subject,
                body=self.body,
                attachments=self.attachment_ids
            )

            email_log.write({'state': 'sent'})
            self.tracking_id.message_post(
                body=_('📧 ส่งเมลติดตามหนี้สำเร็จ<br/>ถึง: %s<br/>หัวข้อ: %s') % (self.email_to, self.subject),
                message_type='notification'
            )
            _logger.info('Email sent successfully via direct SMTP to: %s', self.email_to)

        except Exception as e:
            error_msg = str(e)
            if '10061' in error_msg or 'Connection refused' in error_msg:
                error_msg = 'ไม่สามารถเชื่อมต่อ Mail Server ได้'
            elif 'Authentication' in error_msg or 'auth' in error_msg.lower():
                error_msg = 'การยืนยันตัวตนล้มเหลว'
            elif 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                error_msg = 'หมดเวลาในการเชื่อมต่อ Mail Server'
            _logger.error('Error sending email: %s', str(e))
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
        """ส่งเมลผ่าน SMTP โดยตรง"""
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



class NpdDebtTrackingBaankhiewLostLine(models.Model):
    """รายการค่าปรับหาย - แท็บค่าปรับหาย"""
    _name = 'npd.debt.tracking.baankhiew.lost.line'
    _description = 'รายการค่าปรับหาย'
    _order = 'doc_id'

    tracking_id = fields.Many2one('npd.debt.tracking.baankhiew', string='รายการติดตาม', 
        required=True, ondelete='cascade')
    lost_invoice_id = fields.Many2one('npd.debt.tracking.baankhiew.lost.invoice', string='ใบแจ้งหนี้ค่าปรับหาย',
        required=True, ondelete='cascade')

    # Related fields จาก lost invoice
    doc_id = fields.Char(related='lost_invoice_id.doc_id', string='เลขเอกสาร', store=True)
    arh_date = fields.Date(related='lost_invoice_id.arh_date', string='วันที่', store=True)
    branch_name = fields.Char(related='lost_invoice_id.branch_name', string='สาขา', store=True)
    sale_name = fields.Char(related='lost_invoice_id.sale_name', string='ชื่อเซลล์', store=True)
    date_start = fields.Date(related='lost_invoice_id.date_start', string='เริ่มเช่า', store=True)
    date_return = fields.Date(related='lost_invoice_id.date_return', string='วันคืน', store=True)
    amt_lost_return = fields.Float(related='lost_invoice_id.amt_lost_return', string='ค่าปรับหาย', store=True)
    discount_lost_return = fields.Float(related='lost_invoice_id.discount_lost_return', string='ส่วนลดค่าปรับหาย', store=True)
    net_lost = fields.Float(related='lost_invoice_id.net_lost', string='ปรับหายสุทธิ', store=True)
    vat_7_percent = fields.Float(related='lost_invoice_id.vat_7_percent', string='ภาษี 7%', store=True)
    before_vat = fields.Float(related='lost_invoice_id.before_vat', string='ก่อนภาษี', store=True)
    total_paid = fields.Float(related='lost_invoice_id.total_paid', string='รับชำระ', store=True)
    remaining_balance = fields.Float(related='lost_invoice_id.remaining_balance', string='คงเหลือ', store=True)
    
    # Related field สำหรับรายการสินค้า
    detail_ids = fields.One2many(related='lost_invoice_id.detail_ids', string='รายการสินค้าปรับหาย')

    def action_view_details(self):
        """ดูรายการสินค้าที่ปรับหาย"""
        self.ensure_one()
        return {
            'name': _('รายการสินค้าปรับหาย - %s') % self.doc_id,
            'type': 'ir.actions.act_window',
            'res_model': 'npd.debt.tracking.baankhiew.lost.detail',
            'view_mode': 'tree',
            'domain': [('lost_invoice_id', '=', self.lost_invoice_id.id)],
            'target': 'new',
            'context': {'create': False, 'edit': False, 'delete': False}
        }



class NpdDebtTrackingBaankhiewTaxLine(models.Model):
    """รายการค่า Tax - แท็บค่า Tax"""
    _name = 'npd.debt.tracking.baankhiew.tax.line'
    _description = 'รายการค่า Tax'
    _order = 'invoice_number'

    tracking_id = fields.Many2one('npd.debt.tracking.baankhiew', string='รายการติดตาม', 
        required=True, ondelete='cascade')
    tax_invoice_id = fields.Many2one('npd.debt.tracking.baankhiew.tax.invoice', string='ใบแจ้งหนี้ค่า Tax',
        required=True, ondelete='cascade')

    # Related fields จาก tax invoice
    invoice_number = fields.Char(related='tax_invoice_id.invoice_number', string='เลขที่ใบกำกับเช่า', store=True)
    branch_name = fields.Char(related='tax_invoice_id.branch_name', string='สาขา', store=True)
    cus_fullname = fields.Char(related='tax_invoice_id.cus_fullname', string='ชื่อลูกค้า', store=True)
    cus_cpnname = fields.Char(related='tax_invoice_id.cus_cpnname', string='บริษัท', store=True)
    tax = fields.Float(related='tax_invoice_id.tax', string='Tax', store=True)
    total_debt = fields.Float(related='tax_invoice_id.total_debt', string='ยอดรวม', store=True)
    total_paid = fields.Float(related='tax_invoice_id.total_paid', string='รับชำระ', store=True)
    remaining_balance = fields.Float(related='tax_invoice_id.remaining_balance', string='ค้างชำระสุทธิ', store=True)
    arh_date = fields.Date(related='tax_invoice_id.arh_date', string='วันที่เริ่มหนี้', store=True)
    due_date = fields.Date(related='tax_invoice_id.due_date', string='วันครบกำหนด', store=True)
    debt_duration = fields.Integer(related='tax_invoice_id.debt_duration', string='จำนวนวัน', store=True)
    responsible_party = fields.Char(related='tax_invoice_id.responsible_party', string='ผู้รับผิดชอบ', store=True)
    bill_status = fields.Char(related='tax_invoice_id.bill_status', string='สถานะบิล', store=True)
