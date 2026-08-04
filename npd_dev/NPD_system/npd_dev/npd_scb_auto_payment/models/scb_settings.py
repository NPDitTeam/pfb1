# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

PREFIX = 'npd_scb_auto_payment.'


def _empty(val):
    """ir.config_parameter.get_param() คืน False เมื่อยังไม่เคยตั้งค่าไว้

    ต้องเช็คก่อนแปลงชนิด เพราะ int(False) == 0 (ไม่ throw) ทำให้ค่า default
    ไม่ถูกใช้ และหน้าตั้งค่าจะโชว์ 0 ทุกช่อง
    """
    return val is None or val is False or val == ''


def _b(val, default=False):
    if _empty(val):
        return default
    return str(val).lower() in ('1', 'true', 'yes', 'on')


def _i(val, default=0):
    if _empty(val):
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _f(val, default=0.0):
    if _empty(val):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class ScbPaymentSettings(models.TransientModel):
    _name = 'scb.payment.settings'
    _description = u'ตั้งค่าตรวจสอบการโอนเงิน'

    verify_enabled = fields.Boolean(
        string="เปิดใช้การตรวจสอบการโอนอัตโนมัติ", default=True,
        help="ให้ Scheduled Action ไล่ตรวจใบรับชำระที่ถึงคิว โดยอ่านสลิปที่แนบไว้ด้วย AI "
             "แล้วจับคู่กับรายการเดินบัญชีจริงของธนาคาร")
    verify_lag_days = fields.Integer(
        string="ข้อมูลธนาคารช้ากว่าจริง (วัน)", default=1,
        help="ธนาคารส่งรายการเดินบัญชีช้ากว่าวันที่โอนจริงกี่วัน\n"
             "ค่า 1 = โอนวันนี้ ระบบจะตรวจสอบให้ในวันพรุ่งนี้ (ยึดวันที่ในหน้ารับชำระ)")
    verify_start_date = fields.Date(
        string="เริ่มตรวจสอบใบรับชำระตั้งแต่วันที่",
        help="ยึด 'วันที่' ในหน้ารับชำระ — ใบที่ลงวันที่ก่อนวันนี้ ระบบจะไม่ดึงมาตรวจ"
             "อัตโนมัติ\n"
             "ใช้กันไม่ให้ระบบไล่ตรวจใบเก่าทั้งฐานข้อมูลจนเปลืองโควตา AI\n"
             "เว้นว่าง = ตรวจทุกใบที่ถึงคิว (ไม่แนะนำถ้ามีใบรับชำระเก่าจำนวนมาก)\n"
             "หมายเหตุ: ใบที่อยู่ก่อนวันนี้ยังกดปุ่ม 'ตรวจสอบการโอน' เองได้ตามปกติ")
    # เลือก statement ตาม "สมุดรายวัน" ของใบรับชำระ
    # เพราะเงินค่าประกันเข้าคนละบัญชีธนาคารกับค่าเช่า/ค่าอื่น ๆ
    verify_deposit_journal_keyword = fields.Char(
        string="คำในชื่อสมุดรายวันที่ถือว่าเป็น 'ค่าประกัน'", default="ค่าประกัน",
        help="ถ้าชื่อสมุดรายวันของใบรับชำระมีคำนี้อยู่ ระบบจะไปเทียบกับ statement "
             "ของธนาคารที่เลือกไว้ในช่อง 'สมุดรายวันค่าประกัน'\n"
             "เช่น 'สมุดรายวันรับชำระค่าประกัน'\n"
             "เว้นว่าง = ไม่แยก ใช้ธนาคารเดียวกันหมด")
    verify_bank_deposit = fields.Selection([
        ('scb', 'SCB (statement_SCB)'),
        ('kbank', 'Kbank (Statement_Kbank)'),
        ('ktb', 'กรุงไทย'),
    ], string="สมุดรายวันค่าประกัน → ตรวจกับ", default='kbank', required=True,
        help="เงินค่าประกันเข้าบัญชีธนาคารไหน")
    verify_skip_journal_keywords = fields.Char(
        string="สมุดรายวันที่ไม่ต้องตรวจ (คั่นด้วย ,)", default="ลดหนี้",
        help="ถ้าชื่อสมุดรายวันมีคำเหล่านี้ ระบบจะข้ามการตรวจสอบไปเลย "
             "(สถานะ = 'ไม่ต้องตรวจสอบ')\n"
             "ใช้กับสมุดรายวันที่เป็นการตัดหนี้ในระบบ ไม่ได้รับโอนเงินจริง "
             "เช่น 'สมุดรายวันรับชำระลดหนี้' — statement ของธนาคารไม่มีทางมีรายการนี้ "
             "ตรวจไปก็ขึ้น 'ไม่สำเร็จ' เปล่า ๆ\n"
             "ใส่ได้หลายคำ คั่นด้วยเครื่องหมายจุลภาค เช่น: ลดหนี้,ปรับปรุง")
    verify_skip_slip_keywords = fields.Char(
        string="เลขอ้างอิงในสลิปที่ไม่ต้องตรวจ (คั่นด้วย ,)", default="REF",
        help="ถ้าเลขอ้างอิงในสลิปมีคำเหล่านี้ ระบบจะข้ามการตรวจสอบ "
             "(สถานะ = 'ไม่ต้องตรวจสอบ')\n"
             "ใช้กับ 'สลิปจ่ายบิล' ที่มีเลขอ้างอิงอย่าง REF001 — ธนาคารบันทึกรายการ "
             "พวกนี้ว่า 'รับชำระค่าสินค้าและบริการ' โดยไม่ระบุชื่อผู้โอน "
             "จึงไม่มีชื่อให้เทียบกับสลิปตั้งแต่แรก\n"
             "ระบบดูเฉพาะช่องเลขอ้างอิง (Reference 1 / เลขที่รายการ) ไม่ได้สแกนทั้งสลิป\n"
             "เว้นว่าง = ไม่ข้าม ตรวจทุกใบตามปกติ\n"
             "หมายเหตุ: ต้องอ่านสลิปด้วย AI ก่อนถึงจะรู้ จึงยังใช้โควตา 1 ครั้ง")
    verify_bank_default = fields.Selection([
        ('scb', 'SCB (statement_SCB)'),
        ('kbank', 'Kbank (Statement_Kbank)'),
        ('ktb', 'กรุงไทย'),
    ], string="สมุดรายวันอื่น → ตรวจกับ", default='scb', required=True,
        help="ใบรับชำระที่สมุดรายวันไม่เข้าเงื่อนไขข้างบน (ค่าเช่า/ค่าปรับ/อื่น ๆ) "
             "จะเทียบกับ statement ของธนาคารนี้")
    verify_amount_tolerance = fields.Float(
        string="ผลต่างจำนวนเงินที่ยอมรับ (บาท)", default=0.0, digits=(16, 2),
        help="ยอดในสลิปกับยอดเงินเข้าของธนาคารต่างกันได้ไม่เกินเท่าไร\n"
             "0 = ต้องตรงกันเป๊ะระดับสตางค์ (ค่าเริ่มต้น)\n"
             "ถ้าเจอเคสที่เงินเข้าจริงแต่ต่างกัน 1 สตางค์ (มักเกิดกับรายการที่มี "
             "ภาษีหัก ณ ที่จ่าย เพราะปัดเศษคนละจุด) ค่อยปรับเป็น 0.01")
    verify_date_tolerance = fields.Integer(
        string="ผลต่างวันที่ที่ยอมรับ (วัน)", default=0,
        help="0 = วันที่ต้องตรงกันพอดี\n1 = ยอมให้ธนาคารลงบัญชีคลาดไป 1 วัน "
             "(เช่น โอนดึกแล้วธนาคารลงวันถัดไป)")
    verify_name_threshold = fields.Float(
        string="เกณฑ์ความเหมือนของชื่อ (0-1)", default=0.6,
        help="คะแนนขั้นต่ำที่ถือว่าชื่อผู้โอนในสลิป ตรงกับชื่อในรายการของธนาคาร")
    verify_ai_name_fallback = fields.Boolean(
        string="ให้ AI ช่วยเทียบชื่อข้ามภาษา", default=True,
        help="ถ้าเทียบตัวอักษรไม่ผ่าน ให้ถาม AI อีกครั้งว่าเป็นบริษัทเดียวกันหรือไม่ "
             "(รองรับสลิปภาษาอังกฤษ vs ชื่อไทยที่ธนาคารบันทึก และชื่อที่ธนาคารตัดท้าย)")
    verify_second_pass = fields.Boolean(
        string="ตรวจซ้ำรอบสองเมื่อจับคู่ไม่ได้", default=True,
        help="ถ้ารอบแรกจับคู่กับรายการเดินบัญชีไม่ได้ ให้ AI กลับไป 'อ่านสลิปใหม่' "
             "พร้อมส่งรายการเงินเข้าจริงในบัญชีไปให้ดูประกอบ แล้วชี้เองว่าตรงกับรายการไหน\n"
             "แก้ปัญหาที่พบบ่อย: AI อ่านวันที่จากสลิปผิด (สลิปมีหลายวันที่ / พ.ศ.-ค.ศ. ปนกัน) "
             "และชื่อผู้โอนคนละภาษากับที่ธนาคารบันทึก\n"
             "ระบบยังบังคับว่า 'จำนวนเงินต้องตรง' เสมอ AI จึงชี้มั่วไม่ได้\n"
             "หมายเหตุ: ใช้โควตา AI เพิ่มอีก 1 ครั้งเฉพาะใบที่รอบแรกไม่ผ่าน")
    verify_second_pass_days = fields.Integer(
        string="ช่วงวันที่ให้ AI ดูรอบสอง (± วัน)", default=3,
        help="รอบสองจะส่งรายการเงินเข้าในช่วงกี่วันรอบ ๆ วันที่จากสลิป ให้ AI พิจารณา\n"
             "ตั้งกว้างขึ้นถ้าสลิปมักอ่านวันที่ผิดหลายวัน (แต่ AI จะมีตัวเลือกเยอะขึ้น)")
    verify_allow_no_name = fields.Boolean(
        string="ยอมรับรายการที่ธนาคารไม่ระบุชื่อผู้โอน", default=True,
        help="รายการชำระผ่านบิลเพย์เมนต์/CrossBank ธนาคารมักไม่ระบุชื่อผู้โอน\n"
             "ถ้าติ๊ก: เมื่อยอดและวันที่ตรงกัน และมีรายการเดียวเท่านั้น ให้ถือว่าโอนสำเร็จ")
    verify_retry_failed = fields.Integer(
        string="ลองซ้ำใบที่ไม่สำเร็จ (ครั้ง)", default=3,
        help="ใบที่ผลออกมา 'ไม่สำเร็จ' ระบบจะลองตรวจให้ใหม่ในรอบถัดไป จนครบกี่ครั้ง\n"
             "จำเป็นเพราะรายการเดินบัญชีของวันนั้นอาจเข้ามาไม่ครบตอนตรวจรอบแรก "
             "(statement ดึงทุก 2 ชม.)\n"
             "ครบเพดานแล้วระบบจะหยุด รอให้คนตรวจเอง — กดปุ่ม 'ตรวจสอบการโอนใหม่' "
             "ที่หน้ารับชำระ จะรีเซ็ตตัวนับให้ลองต่อได้\n"
             "0 = ไม่ลองซ้ำเลย (ตรวจครั้งเดียวจบ)\n"
             "หมายเหตุ: การลองซ้ำไม่ได้อ่านสลิปใหม่ (ใช้ค่าที่อ่านไว้แล้ว) "
             "จึงเปลืองโควตา AI เฉพาะรอบตรวจซ้ำรอบสองเท่านั้น")
    verify_batch_limit = fields.Integer(
        string="ตรวจสูงสุดต่อรอบ (ใบ)", default=100,
        help="จำกัดจำนวนใบรับชำระที่ตรวจต่อการทำงาน 1 รอบของ Scheduled Action "
             "(กันเรียก AI ถี่เกินโควตา)")

    pending_count = fields.Integer(
        string="ใบรับชำระที่จะเข้าคิวตรวจ", compute='_compute_pending_count',
        help="จำนวนใบรับชำระที่เข้าเงื่อนไขตามค่าที่กรอกอยู่ตอนนี้ "
             "(อัปเดตทันทีเมื่อเปลี่ยนวันที่เริ่มตรวจ) — ใช้ประเมินโควตา AI ก่อนบันทึก")

    @api.depends('verify_start_date', 'verify_lag_days', 'verify_retry_failed')
    def _compute_pending_count(self):
        Payment = self.env['account.payment']
        pending = ('to_check', 'no_slip', 'waiting', False)
        for rec in self:
            cutoff = fields.Date.context_today(rec) - timedelta(
                days=max(0, rec.verify_lag_days or 0))
            domain = [
                ('payment_type', '=', 'inbound'),
                ('partner_type', '=', 'customer'),
                ('state', '=', 'posted'),
                ('date', '<=', cutoff),
            ]
            if rec.verify_start_date:
                domain.append(('date', '>=', rec.verify_start_date))
            # ให้ตรงกับ _scb_pending_domain() — รวมใบที่ "ไม่สำเร็จ" ที่ยังไม่ครบเพดาน
            retry = max(0, rec.verify_retry_failed or 0)
            if retry > 0:
                domain += ['|',
                           ('scb_verify_state', 'in', pending),
                           '&', ('scb_verify_state', '=', 'failed'),
                                ('scb_verify_attempts', '<', retry)]
            else:
                domain.append(('scb_verify_state', 'in', pending))
            rec.pending_count = Payment.search_count(domain)

    @api.model
    def default_get(self, fields_list):
        res = super(ScbPaymentSettings, self).default_get(fields_list)
        icp = self.env['ir.config_parameter'].sudo()
        res['verify_enabled'] = _b(icp.get_param(PREFIX + 'verify_enabled'), default=True)
        res['verify_lag_days'] = _i(icp.get_param(PREFIX + 'verify_lag_days'), 1)
        # ยังไม่เคยตั้งค่า -> เสนอ "พรุ่งนี้" ให้เลย (ตัดขาดจากใบเก่า ไม่ไล่ย้อนหลัง)
        # ถ้าต้องการตรวจย้อนหลังทั้งหมด ให้ล้างช่องนี้ให้ว่างแล้วบันทึก
        start = icp.get_param(PREFIX + 'verify_start_date')
        res['verify_start_date'] = (
            start if not _empty(start) else fields.Date.today() + timedelta(days=1))
        res['verify_deposit_journal_keyword'] = icp.get_param(
            PREFIX + 'verify_deposit_journal_keyword', default=u'ค่าประกัน')
        res['verify_skip_journal_keywords'] = icp.get_param(
            PREFIX + 'verify_skip_journal_keywords', default=u'ลดหนี้')
        res['verify_skip_slip_keywords'] = icp.get_param(
            PREFIX + 'verify_skip_slip_keywords', default=u'REF')
        res['verify_bank_deposit'] = icp.get_param(
            PREFIX + 'verify_bank_deposit') or 'kbank'
        res['verify_bank_default'] = icp.get_param(
            PREFIX + 'verify_bank_default') or 'scb'
        res['verify_amount_tolerance'] = _f(
            icp.get_param(PREFIX + 'verify_amount_tolerance'), 0.0)
        res['verify_date_tolerance'] = _i(icp.get_param(PREFIX + 'verify_date_tolerance'), 0)
        res['verify_name_threshold'] = _f(icp.get_param(PREFIX + 'verify_name_threshold'), 0.6)
        res['verify_ai_name_fallback'] = _b(
            icp.get_param(PREFIX + 'verify_ai_name_fallback'), default=True)
        res['verify_allow_no_name'] = _b(
            icp.get_param(PREFIX + 'verify_allow_no_name'), default=True)
        res['verify_second_pass'] = _b(
            icp.get_param(PREFIX + 'verify_second_pass'), default=True)
        res['verify_second_pass_days'] = _i(
            icp.get_param(PREFIX + 'verify_second_pass_days'), 3)
        res['verify_batch_limit'] = _i(icp.get_param(PREFIX + 'verify_batch_limit'), 100)
        res['verify_retry_failed'] = _i(icp.get_param(PREFIX + 'verify_retry_failed'), 3)
        return res

    def action_save(self):
        self.ensure_one()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PREFIX + 'verify_enabled', 'True' if self.verify_enabled else 'False')
        icp.set_param(PREFIX + 'verify_lag_days', str(max(0, self.verify_lag_days)))
        icp.set_param(PREFIX + 'verify_start_date',
                      fields.Date.to_string(self.verify_start_date) if self.verify_start_date else '')
        # กฎเลือกธนาคารเปลี่ยน -> ฟิลด์ scb_verify_bank (stored compute) ต้องคำนวณใหม่
        # เพราะ @api.depends ตามค่าใน ir.config_parameter ไม่ได้
        mapping = [
            ('verify_deposit_journal_keyword',
             (self.verify_deposit_journal_keyword or '').strip()),
            ('verify_skip_journal_keywords',
             (self.verify_skip_journal_keywords or '').strip()),
            ('verify_skip_slip_keywords',
             (self.verify_skip_slip_keywords or '').strip()),
            ('verify_bank_deposit', self.verify_bank_deposit or 'kbank'),
            ('verify_bank_default', self.verify_bank_default or 'scb'),
        ]
        mapping_changed = any(
            (icp.get_param(PREFIX + key) or '') != value for key, value in mapping)
        for key, value in mapping:
            icp.set_param(PREFIX + key, value)
        if mapping_changed:
            self._scb_recompute_verify_bank()
        icp.set_param(PREFIX + 'verify_amount_tolerance',
                      str(abs(self.verify_amount_tolerance or 0.0)))
        icp.set_param(PREFIX + 'verify_date_tolerance', str(max(0, self.verify_date_tolerance)))
        icp.set_param(PREFIX + 'verify_name_threshold',
                      str(min(1.0, max(0.0, self.verify_name_threshold or 0.6))))
        icp.set_param(PREFIX + 'verify_ai_name_fallback',
                      'True' if self.verify_ai_name_fallback else 'False')
        icp.set_param(PREFIX + 'verify_allow_no_name',
                      'True' if self.verify_allow_no_name else 'False')
        icp.set_param(PREFIX + 'verify_second_pass',
                      'True' if self.verify_second_pass else 'False')
        icp.set_param(PREFIX + 'verify_second_pass_days',
                      str(max(0, self.verify_second_pass_days or 3)))
        icp.set_param(PREFIX + 'verify_batch_limit', str(max(1, self.verify_batch_limit or 100)))
        icp.set_param(PREFIX + 'verify_retry_failed', str(max(0, self.verify_retry_failed or 0)))
        return {'type': 'ir.actions.act_window_close'}

    def _scb_recompute_verify_bank(self):
        """สั่งคำนวณ 'ธนาคารที่ตรวจ' ใหม่ทั้งหมด หลังกฎเลือกธนาคารเปลี่ยน"""
        Payment = self.env['account.payment'].sudo()
        payments = Payment.search([
            ('payment_type', '=', 'inbound'),
            ('partner_type', '=', 'customer'),
        ])
        if payments:
            self.env.add_to_compute(Payment._fields['scb_verify_bank'], payments)
            payments.flush(['scb_verify_bank'])

    def action_open_bank_statement_config(self):
        """ไปหน้าตั้งค่าการดึงรายการเดินบัญชีจาก Google Sheet"""
        self.ensure_one()
        if 'npd.scb.cashflow.config' not in self.env:
            raise UserError(_("ยังไม่ได้ติดตั้งโมดูล npd_scb_cashflow"))
        return self.env['npd.scb.cashflow.config'].action_open_config()

    def action_run_verify_now(self):
        """ปุ่มทดสอบ: สั่งให้ระบบไล่ตรวจใบรับชำระที่ถึงคิวทันที (ไม่ต้องรอ cron)"""
        self.ensure_one()
        self.env['account.payment']._cron_scb_verify_transfers()
        return {'type': 'ir.actions.act_window_close'}
