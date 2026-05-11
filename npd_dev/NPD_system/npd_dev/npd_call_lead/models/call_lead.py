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


class NpdCallLead(models.Model):
    _name = 'npd.call.lead'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'โทรติดตาม Lead'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(string='ชื่อ', compute='_compute_display_name', store=True)

    @api.depends('lead_id', 'partner_name')
    def _compute_display_name(self):
        for rec in self:
            if rec.lead_id and rec.partner_name:
                rec.display_name = '%s - %s' % (rec.lead_id.name, rec.partner_name)
            elif rec.lead_id:
                rec.display_name = rec.lead_id.name
            else:
                rec.display_name = 'New'

    # ฟิลด์เลือก Lead - กรองเฉพาะสถานะ ใหม่ และ เริ่มติดต่อ
    lead_id = fields.Many2one('crm.lead', string='Lead',
        required=True,
        domain="[('stage_id.name', 'in', ['ใหม่', 'เริ่มติดต่อ', 'New', 'Qualified'])]",
        help='เลือก Lead ที่ต้องการติดตาม (เฉพาะสถานะ ใหม่ และ เริ่มติดต่อ)')

    partner_id = fields.Many2one(related='lead_id.partner_id', string='ลูกค้า', store=True)
    partner_name = fields.Char(string='ชื่อลูกค้า', compute='_compute_partner_info', store=True)
    partner_phone = fields.Char(string='เบอร์โทรศัพท์', store=True)
    partner_mobile = fields.Char(string='มือถือ', store=True)
    partner_email = fields.Char(string='อีเมล', store=True)
    partner_street = fields.Char(related='partner_id.street', string='ที่อยู่')
    partner_street2 = fields.Char(related='partner_id.street2', string='ที่อยู่ 2')
    partner_city = fields.Char(related='partner_id.city', string='เมือง')
    partner_state_id = fields.Many2one(related='partner_id.state_id', string='จังหวัด')
    partner_zip = fields.Char(related='partner_id.zip', string='รหัสไปรษณีย์')

    # ข้อมูล Lead
    lead_name = fields.Char(related='lead_id.name', string='ชื่อ Lead', store=True)
    lead_stage_id = fields.Many2one(related='lead_id.stage_id', string='Stage', store=True)
    lead_expected_revenue = fields.Monetary(related='lead_id.expected_revenue', string='รายได้ที่คาดหวัง', store=True)
    lead_probability = fields.Float(related='lead_id.probability', string='ความน่าจะเป็น (%)', store=True)
    lead_user_id = fields.Many2one(related='lead_id.user_id', string='พนักงานขาย', store=True)
    lead_description = fields.Text(related='lead_id.description', string='รายละเอียด Lead')
    currency_id = fields.Many2one(related='lead_id.company_currency', string='สกุลเงิน', store=True)

    state = fields.Selection([
        ('draft', 'รอดำเนินการ'),
        ('in_progress', 'กำลังติดตาม'),
        ('done', 'เสร็จสิ้น'),
        ('cancel', 'ยกเลิก')
    ], string='สถานะ', default='draft', tracking=True)

    tracking_date = fields.Date(string='วันที่ติดตาม', default=fields.Date.today)
    note = fields.Text(string='หมายเหตุ')

    call_log_ids = fields.One2many('npd.call.lead.log', 'tracking_id', string='ประวัติการโทร')
    call_count = fields.Integer(string='จำนวนครั้งที่โทร', compute='_compute_call_count')

    # Email Log
    email_log_ids = fields.One2many('npd.call.lead.email.log', 'tracking_id', string='ประวัติการส่งเมล')
    email_count = fields.Integer(string='จำนวนครั้งที่ส่งเมล', compute='_compute_email_count')

    @api.depends('lead_id', 'lead_id.partner_name', 'lead_id.contact_name')
    def _compute_partner_info(self):
        for rec in self:
            if rec.lead_id:
                rec.partner_name = rec.lead_id.partner_name or rec.lead_id.contact_name or ''
            else:
                rec.partner_name = ''

    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        if self.lead_id:
            # ดึงเบอร์โทรศัพท์และอีเมลจาก Lead มาใส่ให้อัตโนมัติ
            self.partner_phone = self.lead_id.phone or ''
            self.partner_mobile = self.lead_id.mobile or ''
            self.partner_email = self.lead_id.email_from or ''

    @api.depends('call_log_ids')
    def _compute_call_count(self):
        for rec in self:
            rec.call_count = len(rec.call_log_ids)

    @api.depends('email_log_ids')
    def _compute_email_count(self):
        for rec in self:
            rec.email_count = len(rec.email_log_ids)

    def action_send_email(self):
        """เปิด popup ส่งเมลติดตาม Lead"""
        self.ensure_one()
        if not self.partner_email:
            raise UserError(_('ไม่พบอีเมลของลูกค้า กรุณาเพิ่มอีเมลในข้อมูลลูกค้าก่อน'))

        # อัพเดทสถานะ
        if self.state == 'draft':
            self.state = 'in_progress'

        # สร้าง default message
        default_subject = 'ติดตาม Lead - %s' % self.lead_id.name
        default_body = """เรียน คุณ%s

ทางบริษัทขอติดต่อเพื่อติดตามความสนใจของท่านเกี่ยวกับ %s

รายละเอียด:
- Lead: %s
- รายได้ที่คาดหวัง: %s บาท

หากท่านมีข้อสงสัยหรือต้องการข้อมูลเพิ่มเติม กรุณาติดต่อกลับ

ขอบคุณครับ/ค่ะ
ฝ่ายขาย
NPD Group""" % (
            self.partner_name or '',
            self.lead_id.name,
            self.lead_id.name,
            '{:,.2f}'.format(self.lead_expected_revenue or 0)
        )

        return {
            'name': _('📧 ส่งเมลติดตาม Lead'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.call.lead.send.email.wizard',
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
            }
        }

    def action_view_email_logs(self):
        """ดูประวัติการส่งเมล"""
        self.ensure_one()
        return {
            'name': _('ประวัติการส่งเมล'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.call.lead.email.log',
            'view_mode': 'tree,form',
            'domain': [('tracking_id', '=', self.id)],
        }

    def action_call_phone(self):
        """กดโทรหาลูกค้า - เปิดหน้าต่างบันทึกการโทร"""
        self.ensure_one()
        # ใช้ partner_phone (โทรศัพท์) เป็นหลัก ถ้าไม่มีค่อยใช้ partner_mobile
        phone = self.partner_phone if self.partner_phone else self.partner_mobile
        if not phone:
            raise UserError(_('ไม่พบเบอร์โทรศัพท์ของลูกค้า'))
        if self.state == 'draft':
            self.state = 'in_progress'
        call_log = self.env['npd.call.lead.log'].create({
            'tracking_id': self.id,
            'call_date': fields.Datetime.now(),
            'phone_number': phone,
            'user_id': self.env.user.id,
            'call_start_time': fields.Datetime.now(),  # บันทึกเวลาเริ่มโทรทันที
        })
        return {
            'name': _('โทรหาลูกค้า'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.call.lead.log',
            'res_id': call_log.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_tracking_id': self.id, 'default_phone_number': phone, 'form_view_initial_mode': 'edit'}
        }

    def action_call_mobile(self):
        """เปิด popup โทรหาลูกค้า"""
        self.ensure_one()
        # ใช้ partner_phone (โทรศัพท์) เป็นหลัก ถ้าไม่มีค่อยใช้ partner_mobile
        phone = self.partner_phone if self.partner_phone else self.partner_mobile
        if not phone:
            raise UserError(_('ไม่พบเบอร์โทรศัพท์ของลูกค้า'))

        active_call = self.call_log_ids.filtered(lambda l: l.is_calling)
        if active_call:
            return {
                'name': _('📞 กำลังโทร - %s') % self.partner_name,
                'type': 'ir.actions.act_window',
                'res_model': 'npd.call.lead.log',
                'res_id': active_call[0].id,
                'view_mode': 'form',
                'views': [(self.env.ref('npd_call_lead.npd_call_lead_log_calling_form').id, 'form')],
                'target': 'new',
            }

        pending_call = self.call_log_ids.filtered(lambda l: not l.is_calling and not l.call_result)
        if pending_call:
            return {
                'name': _('📞 โทรหาลูกค้า - %s') % self.partner_name,
                'type': 'ir.actions.act_window',
                'res_model': 'npd.call.lead.log',
                'res_id': pending_call[0].id,
                'view_mode': 'form',
                'views': [(self.env.ref('npd_call_lead.npd_call_lead_log_calling_form').id, 'form')],
                'target': 'new',
            }

        clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
        if clean_phone.startswith('0'):
            clean_phone = '+66' + clean_phone[1:]
        elif not clean_phone.startswith('+'):
            clean_phone = '+66' + clean_phone

        if self.state == 'draft':
            self.state = 'in_progress'

        call_log = self.env['npd.call.lead.log'].create({
            'tracking_id': self.id,
            'call_date': fields.Datetime.now(),
            'phone_number': phone,
            'clean_phone': clean_phone,
            'user_id': self.env.user.id,
            'call_start_time': fields.Datetime.now(),  # บันทึกเวลาเริ่มโทรทันที
            'is_calling': False,
        })

        return {
            'name': _('📞 โทรหาลูกค้า - %s') % self.partner_name,
            'type': 'ir.actions.act_window',
            'res_model': 'npd.call.lead.log',
            'res_id': call_log.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_call_lead.npd_call_lead_log_calling_form').id, 'form')],
            'target': 'new',
        }

    def action_done(self):
        """จบงานติดตาม Lead วันนี้"""
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

    def action_view_lead(self):
        self.ensure_one()
        return {
            'name': _('Lead'),
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': self.lead_id.id,
            'view_mode': 'form',
        }

    def action_view_call_logs(self):
        self.ensure_one()
        return {
            'name': _('ประวัติการโทร'),
            'type': 'ir.actions.act_window',
            'res_model': 'npd.call.lead.log',
            'view_mode': 'tree,form',
            'domain': [('tracking_id', '=', self.id)],
        }


class NpdCallLeadLog(models.Model):
    _name = 'npd.call.lead.log'
    _description = 'ประวัติการโทรติดตาม Lead'
    _order = 'call_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(string='ชื่อ', compute='_compute_display_name', store=True)

    @api.depends('partner_name', 'call_date')
    def _compute_display_name(self):
        for rec in self:
            if rec.partner_name and rec.call_date:
                rec.display_name = '%s - %s' % (rec.partner_name, rec.call_date.strftime('%d/%m/%Y %H:%M'))
            else:
                rec.display_name = 'New Call'

    tracking_id = fields.Many2one('npd.call.lead', string='รายการติดตาม', required=True, ondelete='cascade')
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
        ('interested', 'สนใจ'),
        ('not_interested', 'ไม่สนใจ'),
        ('callback', 'นัดโทรกลับ'),
        ('other', 'อื่นๆ')
    ], string='ผลการโทร')
    note = fields.Text(string='บันทึกการโทร')

    lead_id = fields.Many2one(related='tracking_id.lead_id', string='Lead', store=True)
    partner_id = fields.Many2one(related='tracking_id.partner_id', string='ลูกค้า', store=True)
    partner_name = fields.Char(related='tracking_id.partner_name', string='ชื่อลูกค้า', store=True)
    partner_email = fields.Char(related='tracking_id.partner_email', string='อีเมล')
    partner_phone = fields.Char(related='tracking_id.partner_phone', string='โทรศัพท์')
    partner_mobile = fields.Char(related='tracking_id.partner_mobile', string='มือถือ')
    partner_street = fields.Char(related='partner_id.street', string='ที่อยู่')
    partner_city = fields.Char(related='partner_id.city', string='เมือง')
    partner_state_id = fields.Many2one(related='partner_id.state_id', string='จังหวัด')
    lead_expected_revenue = fields.Monetary(related='tracking_id.lead_expected_revenue', string='รายได้ที่คาดหวัง')
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
        # ใช้ partner_phone (โทรศัพท์) เป็นหลัก ถ้าไม่มีค่อยใช้ partner_mobile
        phone = self.clean_phone or self.phone_number or self.partner_phone or self.partner_mobile
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
            'res_model': 'npd.call.lead.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_call_lead.npd_call_lead_log_calling_form').id, 'form')],
            'target': 'new',
        }

    def action_start_calling(self):
        self.ensure_one()
        self.write({'call_start_time': fields.Datetime.now(), 'is_calling': True})
        return {
            'name': _('📞 กำลังโทร - %s') % self.partner_name,
            'type': 'ir.actions.act_window',
            'res_model': 'npd.call.lead.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_call_lead.npd_call_lead_log_calling_form').id, 'form')],
            'target': 'new',
        }

    def action_start_timer(self):
        self.ensure_one()
        # ใช้ partner_phone (โทรศัพท์) เป็นหลัก ถ้าไม่มีค่อยใช้ partner_mobile
        phone = self.clean_phone or self.phone_number or self.partner_phone or self.partner_mobile
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
            'res_model': 'npd.call.lead.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_call_lead.npd_call_lead_log_calling_form').id, 'form')],
            'target': 'new',
        }

    def action_make_call(self):
        self.ensure_one()
        # ใช้ partner_phone (โทรศัพท์) เป็นหลัก ถ้าไม่มีค่อยใช้ partner_mobile
        phone = self.clean_phone or self.phone_number or self.partner_phone or self.partner_mobile
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
            'res_model': 'npd.call.lead.log',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('npd_call_lead.npd_call_lead_log_calling_form').id, 'form')],
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
            'res_model': 'npd.call.lead.log',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('npd_call_lead.npd_call_lead_log_result_form').id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'}
        }

    def action_save_and_close(self):
        self.ensure_one()
        if not self.call_result:
            raise UserError(_('⚠️ กรุณาเลือกผลการโทรก่อนบันทึก'))
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel_call(self):
        """ยกเลิกการโทร - ลบประวัติการโทรที่ยังไม่มีผลการโทร"""
        self.ensure_one()
        # ลบ call_log ที่ยังไม่มี call_result
        if not self.call_result:
            self.unlink()
        return {'type': 'ir.actions.act_window_close'}

    def js_start_call(self):
        self.ensure_one()
        # ใช้ partner_phone (โทรศัพท์) เป็นหลัก ถ้าไม่มีค่อยใช้ partner_mobile
        phone = self.clean_phone or self.phone_number or self.partner_phone or self.partner_mobile
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

    def js_end_call(self):
        self.ensure_one()
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
                'res_model': 'npd.call.lead.log',
                'res_id': self.id,
                'view_mode': 'form',
                'view_id': self.env.ref('npd_call_lead.npd_call_lead_log_result_form').id,
                'target': 'new',
                'context': {'form_view_initial_mode': 'edit'}
            }
        }


class NpdCallLeadEmailLog(models.Model):
    _name = 'npd.call.lead.email.log'
    _description = 'ประวัติการส่งเมลติดตาม Lead'
    _order = 'send_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(string='ชื่อ', compute='_compute_display_name', store=True)

    @api.depends('partner_name', 'send_date')
    def _compute_display_name(self):
        for rec in self:
            if rec.partner_name and rec.send_date:
                rec.display_name = '%s - %s' % (rec.partner_name, rec.send_date.strftime('%d/%m/%Y %H:%M'))
            else:
                rec.display_name = 'New Email'

    tracking_id = fields.Many2one('npd.call.lead', string='รายการติดตาม', required=True, ondelete='cascade')
    send_date = fields.Datetime(string='วันเวลาที่ส่ง', default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string='ผู้ส่ง', default=lambda self: self.env.user)

    email_from = fields.Char(string='จากอีเมล', required=True)
    email_to = fields.Char(string='ถึงอีเมล', required=True)
    subject = fields.Char(string='หัวข้อ', required=True)
    body = fields.Text(string='เนื้อหา')

    attachment_ids = fields.Many2many('ir.attachment', 'call_lead_email_log_attachment_rel', 'email_log_id',
        'attachment_id', string='ไฟล์แนบ')
    attachment_count = fields.Integer(string='จำนวนไฟล์แนบ', compute='_compute_attachment_count')

    state = fields.Selection([
        ('draft', 'รอส่ง'),
        ('sent', 'ส่งสำเร็จ'),
        ('failed', 'ส่งไม่สำเร็จ')
    ], string='สถานะ', default='draft')
    error_message = fields.Text(string='ข้อผิดพลาด')

    lead_id = fields.Many2one(related='tracking_id.lead_id', string='Lead', store=True)
    partner_id = fields.Many2one(related='tracking_id.partner_id', string='ลูกค้า', store=True)
    partner_name = fields.Char(related='tracking_id.partner_name', string='ชื่อลูกค้า', store=True)
    lead_expected_revenue = fields.Monetary(related='tracking_id.lead_expected_revenue', string='รายได้ที่คาดหวัง')
    currency_id = fields.Many2one(related='tracking_id.currency_id', string='สกุลเงิน')

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)


class NpdCallLeadSendEmailWizard(models.TransientModel):
    _name = 'npd.call.lead.send.email.wizard'
    _description = 'Wizard ส่งเมลติดตาม Lead'

    # ค่า SMTP สำหรับส่งเมลโดยตรง (ไม่ผ่าน Odoo Outgoing Mail Server)
    SMTP_HOST = 'smtp.gmail.com'
    SMTP_PORT = 587
    SMTP_USER = 'npdsgroup.official@gmail.com'
    SMTP_PASS = 'yekp enim vkuy gyjc'  # App Password
    SMTP_ENCRYPTION = 'starttls'

    tracking_id = fields.Many2one('npd.call.lead', string='รายการติดตาม', required=True)
    partner_id = fields.Many2one('res.partner', string='ลูกค้า')
    partner_name = fields.Char(string='ชื่อลูกค้า')
    partner_email = fields.Char(string='อีเมลลูกค้า')

    email_from = fields.Char(string='จากอีเมล', required=True, default='npdsgroup.official@gmail.com')
    email_to = fields.Char(string='ถึงอีเมล', required=True)
    subject = fields.Char(string='หัวข้อ', required=True)
    body = fields.Text(string='เนื้อหา', required=True)

    attachment_ids = fields.Many2many('ir.attachment', 'call_lead_wizard_attachment_rel', 'wizard_id',
        'attachment_id', string='ไฟล์แนบ')

    @api.model
    def default_get(self, fields_list):
        res = super(NpdCallLeadSendEmailWizard, self).default_get(fields_list)
        if res.get('partner_email'):
            res['email_to'] = res['partner_email']
        return res

    def action_send_email(self):
        """ส่งเมลและบันทึกประวัติ - ส่งผ่าน SMTP โดยตรงจากโมดูล"""
        self.ensure_one()

        if not self.email_to:
            raise UserError(_('กรุณาระบุอีเมลผู้รับ'))

        # สร้าง Email Log ก่อน
        email_log = self.env['npd.call.lead.email.log'].create({
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
                body=_('📧 ส่งเมลติดตาม Lead สำเร็จ<br/>ถึง: %s<br/>หัวข้อ: %s') % (self.email_to, self.subject),
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
                'message': _('ส่งเมลติดตาม Lead เรียบร้อยแล้ว'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _send_email_direct_smtp(self, email_from, email_to, subject, body, attachments=None):
        """ส่งเมลผ่าน SMTP โดยตรง ไม่ผ่าน Odoo mail queue - ใช้ค่า SMTP จาก class constants"""
        # ใช้ค่า SMTP จาก class constants
        smtp_host = self.SMTP_HOST
        smtp_port = self.SMTP_PORT
        smtp_user = self.SMTP_USER
        smtp_pass = self.SMTP_PASS
        smtp_encryption = self.SMTP_ENCRYPTION

        _logger.info('Sending email via direct SMTP: host=%s, port=%s, user=%s, encryption=%s',
                     smtp_host, smtp_port, smtp_user, smtp_encryption)

        # สร้าง email message
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = email_to
        msg['Subject'] = subject

        # แปลง body เป็น HTML
        body_html = '<html><body><pre style="font-family: Tahoma, sans-serif;">{}</pre></body></html>'.format(
            body.replace('\n', '<br/>')
        )
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        # แนบไฟล์
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

        # เชื่อมต่อและส่งเมล
        try:
            if smtp_encryption == 'ssl':
                # SSL connection
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
            else:
                # Plain or STARTTLS connection
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                if smtp_encryption == 'starttls':
                    server.starttls()

            # Login
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)

            # ส่งเมล
            server.sendmail(email_from, [email_to], msg.as_string())
            server.quit()

            _logger.info('Email sent successfully to: %s', email_to)

        except smtplib.SMTPAuthenticationError as e:
            _logger.error('SMTP Authentication Error: %s', str(e))
            raise UserError(_('การยืนยันตัวตน SMTP ล้มเหลว: กรุณาตรวจสอบ Username และ Password'))
        except smtplib.SMTPConnectError as e:
            _logger.error('SMTP Connect Error: %s', str(e))
            raise UserError(_('ไม่สามารถเชื่อมต่อ SMTP Server: %s') % str(e))
        except smtplib.SMTPException as e:
            _logger.error('SMTP Error: %s', str(e))
            raise UserError(_('เกิดข้อผิดพลาด SMTP: %s') % str(e))
        except Exception as e:
            _logger.error('General Error sending email: %s', str(e))
            raise
