# -*- coding: utf-8 -*-
"""จุดเชื่อมระหว่างห้องแชทกับ "ตัวช่วย AI-IT"

ใช้วิธีเดียวกับ OdooBot คือดักที่ _message_post_after_hook แล้วให้บอทตอบกลับ
ต่างกันตรงที่ดักเฉพาะ mail.channel (ไม่ใช่ทุกโมเดลที่มี chatter)
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MailChannel(models.Model):
    _inherit = 'mail.channel'

    def _message_post_after_hook(self, message, msg_vals):
        result = super(MailChannel, self)._message_post_after_hook(message, msg_vals)
        if len(self) == 1 and not self.env.context.get('npd_ai_it_bot'):
            try:
                self.env['npd.ai.it.session']._on_channel_message(self, message, msg_vals)
            except Exception:  # noqa: BLE001 - ห้ามให้ข้อความของพนักงานหายไป
                _logger.exception('ตัวช่วย AI-IT: ตอบกลับในห้อง %s ไม่สำเร็จ', self.id)
        return result
