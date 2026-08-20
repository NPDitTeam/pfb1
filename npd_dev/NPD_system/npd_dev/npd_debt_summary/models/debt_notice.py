# -*- coding: utf-8 -*-
"""ขั้นการออกหนังสือทวงถาม (Notice)

ผู้ใช้ระบุ 20 ส.ค. 2026:
  - ต้องกดปุ่ม "เริ่มออก Notice" ก่อน ระบบถึงเริ่มนับ ไม่ได้นับอัตโนมัติทุกราย
  - กดแล้วเป็น Notice 1 นับไป 14 วัน
  - ครบ 14 วันแล้วยังมีหนี้ค้างเหลืออยู่ -> Notice 2 นับต่ออีก 14 วัน
  - ครบอีกรอบยังค้าง -> Notice นิติกร (ขั้นสุดท้าย ไม่เลื่อนต่อ)
  - แสดงสถานะและวันคงเหลือในหน้าตาราง

การเลื่อนขั้นทำตอน cron อัพเดทประจำวัน (cron_refresh_all) ซึ่งรันอยู่แล้วทุกวันตี 3
โดยเลื่อนหลังจากดึงยอดหนี้ใหม่เสร็จ ยอดที่ใช้ตัดสินจึงเป็นยอดล่าสุดเสมอ
ลูกค้าที่ชำระครบจะถูกลบออกจากรายการโดย _remove_empty_records อยู่แล้ว
สถานะ Notice ของรายนั้นจึงหายไปพร้อมกัน
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# จำนวนวันของแต่ละขั้น
NOTICE_DAYS = 14

# ขั้นถัดไปของแต่ละขั้น (ขั้นที่ไม่มีอยู่ในตาราง = ไม่เลื่อนต่อ)
NEXT_STAGE = {
    'notice1': 'notice2',
    'notice2': 'legal',
}


class NpdDebtSummaryNotice(models.Model):
    _inherit = 'npd.debt.summary'

    notice_stage = fields.Selection([
        ('none', 'ยังไม่ออก Notice'),
        ('notice1', 'Notice 1'),
        ('notice2', 'Notice 2'),
        ('legal', 'Notice นิติกร'),
    ], string='ขั้น Notice', default='none', copy=False, index=True, readonly=True)
    notice_start_date = fields.Date(string='วันที่เริ่มออก Notice', readonly=True, copy=False,
                                    help='วันที่กดปุ่มเริ่มออก Notice ครั้งแรก')
    notice_date = fields.Date(string='วันที่ออก Notice ขั้นนี้', readonly=True, copy=False)
    notice_due_date = fields.Date(string='ครบกำหนด Notice', readonly=True, copy=False,
                                  help='ครบกำหนดแล้วยังค้างชำระ ระบบจะเลื่อนไปขั้นถัดไปให้เอง')
    notice_days_left = fields.Integer(string='วันคงเหลือ (Notice)',
                                      compute='_compute_notice_days_left',
                                      help='ติดลบ = เลยกำหนดแล้ว รอ cron รอบถัดไปเลื่อนขั้น')

    notice_days_label = fields.Char(string='สถานะวัน (Notice)',
                                    compute='_compute_notice_days_left',
                                    help='ขั้นนิติกรจะไม่ถูกเลื่อนต่อ ตัวเลขจึงเดินสะสมไปเรื่อย ๆ '
                                         'ว่าเลยกำหนดมากี่วันแล้ว')

    @api.depends('notice_due_date', 'notice_stage')
    def _compute_notice_days_left(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.notice_stage in ('none', False) or not rec.notice_due_date:
                rec.notice_days_left = 0
                rec.notice_days_label = ''
                continue
            days = (rec.notice_due_date - today).days
            rec.notice_days_left = days
            if days > 0:
                rec.notice_days_label = u'เหลือ %d วัน' % days
            elif days == 0:
                rec.notice_days_label = u'ครบกำหนดวันนี้'
            else:
                # ขั้นนิติกรจะค้างอยู่ตรงนี้ตลอด ตัวเลขจึงเดินขึ้นไปเรื่อย ๆ
                rec.notice_days_label = u'เกินกำหนด %d วัน' % abs(days)

    # ------------------------------------------------------------------
    # ปุ่มบนฟอร์ม
    # ------------------------------------------------------------------
    def _set_notice_stage(self, stage):
        """ตั้งขั้น Notice พร้อมเริ่มนับ 14 วันใหม่"""
        today = fields.Date.context_today(self)
        vals = {
            'notice_stage': stage,
            'notice_date': today,
            'notice_due_date': today + timedelta(days=NOTICE_DAYS),
        }
        for rec in self:
            if not rec.notice_start_date:
                rec.write(dict(vals, notice_start_date=today))
            else:
                rec.write(vals)

    def action_start_notice(self):
        """ปุ่ม 'เริ่มออก Notice' -- เริ่มที่ Notice 1 แล้วนับ 14 วัน"""
        self._set_notice_stage('notice1')
        return True

    def action_reset_notice(self):
        """ยกเลิกการออก Notice (กดผิด/ตกลงกันได้แล้ว) กลับไปยังไม่เริ่มนับ"""
        self.write({
            'notice_stage': 'none',
            'notice_start_date': False,
            'notice_date': False,
            'notice_due_date': False,
        })
        return True

    # ------------------------------------------------------------------
    # เลื่อนขั้นอัตโนมัติ (เรียกจาก cron ประจำวัน)
    # ------------------------------------------------------------------
    @api.model
    def _escalate_notices(self):
        """เลื่อนขั้น Notice ให้รายที่ครบกำหนดแล้วยังมีหนี้ค้างอยู่"""
        today = fields.Date.context_today(self)
        records = self.search([
            ('notice_stage', 'in', list(NEXT_STAGE.keys())),
            ('notice_due_date', '<=', today),
        ])
        moved = 0
        for rec in records:
            if (rec.grand_total or 0.0) <= 0.005:
                continue          # ชำระครบแล้ว ไม่ต้องเลื่อนขั้น
            rec._set_notice_stage(NEXT_STAGE[rec.notice_stage])
            moved += 1
        if moved:
            _logger.info('npd_debt_summary: เลื่อนขั้น Notice %s ราย', moved)
        return moved

    @api.model
    def cron_refresh_all(self):
        """cron ประจำวัน: ดึงยอดหนี้ใหม่ก่อน แล้วค่อยเลื่อนขั้น Notice"""
        res = super(NpdDebtSummaryNotice, self).cron_refresh_all()
        self._escalate_notices()
        return res
