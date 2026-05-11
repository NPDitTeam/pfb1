# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class CrmLeadCallButton(models.Model):
    _inherit = 'crm.lead'

    def action_call_lead_phone(self):
        """โทรหาลูกค้าจากหน้า CRM Lead"""
        self.ensure_one()
        phone = self.phone or self.mobile
        if not phone:
            raise UserError(_('ไม่พบเบอร์โทรศัพท์ของลูกค้า'))

        # ค้นหาหรือสร้าง npd.call.lead record
        call_lead = self.env['npd.call.lead'].search([
            ('lead_id', '=', self.id),
            ('state', '!=', 'done')
        ], limit=1)

        if not call_lead:
            # สร้าง record ใหม่
            call_lead = self.env['npd.call.lead'].create({
                'lead_id': self.id,
                'partner_phone': self.phone or '',
                'partner_mobile': self.mobile or '',
                'partner_email': self.email_from or '',
                'tracking_date': fields.Date.today(),
            })

        # เรียกใช้ action_call_mobile จาก npd.call.lead
        return call_lead.action_call_mobile()

    def action_send_lead_email(self):
        """ส่งเมลติดตาม Lead จากหน้า CRM Lead"""
        self.ensure_one()
        if not self.email_from:
            raise UserError(_('ไม่พบอีเมลของลูกค้า กรุณาเพิ่มอีเมลในข้อมูลลูกค้าก่อน'))

        # ค้นหาหรือสร้าง npd.call.lead record
        call_lead = self.env['npd.call.lead'].search([
            ('lead_id', '=', self.id),
            ('state', '!=', 'done')
        ], limit=1)

        if not call_lead:
            # สร้าง record ใหม่
            call_lead = self.env['npd.call.lead'].create({
                'lead_id': self.id,
                'partner_phone': self.phone or '',
                'partner_mobile': self.mobile or '',
                'partner_email': self.email_from or '',
                'tracking_date': fields.Date.today(),
            })

        # เรียกใช้ action_send_email จาก npd.call.lead
        return call_lead.action_send_email()
