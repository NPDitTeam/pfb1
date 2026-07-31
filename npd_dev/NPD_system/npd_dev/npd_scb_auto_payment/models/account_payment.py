# -*- coding: utf-8 -*-
u"""ตรวจสอบ "การโอนเงินจริง" ของใบรับชำระ (account.payment)

แนวคิด (แทนของเดิมที่ยึดใบแจ้งหนี้ + สร้างใบรับชำระให้อัตโนมัติ):

1. พนักงานสร้างใบรับชำระเองตามปกติ แล้วแนบ "สลิปโอนเงิน" ไว้ในเอกสารแนบ
2. AI (Gemini ตัวเดียวกับปุ่ม "ใช้วันที่จากสลิป") อ่านสลิป -> ได้ วันที่ / จำนวนเงิน /
   ชื่อผู้โอน
3. เอาค่าที่ได้ไปจับคู่กับ "รายการเดินบัญชีจริงของธนาคาร" (npd.scb.bank.statement
   ที่ดึงจากแท็บ statement_* ใน Google Sheet)
4. ข้อมูลจากธนาคารมาช้ากว่าจริง ~1 วัน จึงตรวจสอบเมื่อ "วันที่ในใบรับชำระ" ผ่านไปแล้ว
   อย่างน้อย 1 วัน (โอนวันนี้ -> ตรวจพรุ่งนี้)
5. ผลลัพธ์แสดงบนหน้ารับชำระ: โอนสำเร็จ / ไม่สำเร็จ (พร้อมเหตุผล)

เงื่อนไขที่ต้องตรงกัน: ชื่อบริษัทผู้โอน (ไทยหรืออังกฤษก็ได้) + จำนวนเงิน + วันที่
"""
import json
import logging
import re
from datetime import timedelta

import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

# ไฟล์แนบที่ส่งให้ AI อ่านได้ (สลิปมีทั้งรูปถ่ายและ PDF จากธนาคาร)
SLIP_MIMETYPES = (
    'image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp',
    'application/pdf',
)

# ค่าเริ่มต้นของการตั้งค่า (ทับได้ที่ ตรวจสอบการโอนเงิน > ตั้งค่า)
DEFAULTS = {
    'verify_enabled': True,
    'verify_lag_days': 1,
    # เลือก statement ที่จะเทียบ "ตามสมุดรายวันของใบรับชำระ"
    #   สมุดรายวันที่มีคำว่า 'ค่าประกัน' -> เงินเข้าบัญชี Kbank
    #   สมุดรายวันอื่น                  -> เงินเข้าบัญชี SCB
    'verify_bank_default': 'scb',
    'verify_bank_deposit': 'kbank',
    'verify_deposit_journal_keyword': u'ค่าประกัน',
    'verify_amount_tolerance': 0.0,   # 0 = จำนวนเงินต้องตรงกันเป๊ะระดับสตางค์
    'verify_date_tolerance': 0,
    'verify_name_threshold': 0.6,
    'verify_ai_name_fallback': True,
    'verify_allow_no_name': True,
    'verify_batch_limit': 100,
    'verify_second_pass': True,
    'verify_second_pass_days': 3,
    'verify_retry_failed': 3,
}


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # ------------------------------------------------------------------
    # ผลการตรวจสอบการโอน
    # ------------------------------------------------------------------
    scb_verify_state = fields.Selection([
        ('to_check', u'รอตรวจสอบ'),
        ('no_slip', u'ยังไม่แนบสลิป'),
        ('waiting', u'รอข้อมูลจากธนาคาร'),
        ('success', u'โอนสำเร็จ'),
        ('failed', u'ไม่สำเร็จ'),
    ], string=u"สถานะการโอน (ธนาคาร)", default='to_check', copy=False, index=True,
        readonly=True,
        help=u"ผลการจับคู่สลิปที่แนบไว้ กับรายการเดินบัญชีจริงของธนาคาร")
    scb_verify_bank = fields.Selection([
        ('scb', 'SCB'),
        ('kbank', 'Kbank'),
        ('ktb', u'กรุงไทย'),
    ], string=u"ธนาคารที่ตรวจ", compute='_compute_scb_verify_bank', store=True,
        help=u"statement ของธนาคารที่ระบบใช้เทียบกับใบรับชำระใบนี้ "
             u"— เลือกจากสมุดรายวัน (ตั้งกฎได้ที่หน้าตั้งค่า)")
    scb_verify_reason = fields.Text(
        string=u"เหตุผล / รายละเอียดผลตรวจ", readonly=True, copy=False)
    scb_verify_datetime = fields.Datetime(
        string=u"ตรวจสอบเมื่อ", readonly=True, copy=False)
    scb_verify_attempts = fields.Integer(
        string=u"จำนวนครั้งที่ตรวจแล้วไม่สำเร็จ", readonly=True, copy=False, default=0,
        help=u"นับเฉพาะครั้งที่ผลออกมา 'ไม่สำเร็จ' — ระบบจะลองซ้ำให้อัตโนมัติจนครบเพดาน "
             u"ที่ตั้งไว้ (เผื่อรายการเดินบัญชีของวันนั้นเข้ามาไม่ครบตอนตรวจรอบแรก) "
             u"ครบแล้วจะหยุดและรอให้คนตรวจเอง\n"
             u"สถานะ 'รอข้อมูลจากธนาคาร' ไม่นับ และจะถูกตรวจซ้ำเรื่อย ๆ")
    scb_statement_id = fields.Many2one(
        'npd.scb.bank.statement', string=u"รายการเดินบัญชีที่จับคู่ได้",
        readonly=True, copy=False, ondelete='set null', index=True)

    # ---- ค่าที่ AI อ่านได้จากสลิป (เก็บไว้ไม่ต้องเรียก AI ซ้ำตอนตรวจรอบถัดไป) ----
    scb_slip_read = fields.Boolean(
        string=u"อ่านสลิปแล้ว", readonly=True, copy=False, default=False)
    scb_slip_date = fields.Date(string=u"วันที่จากสลิป", readonly=True, copy=False)
    scb_slip_amount = fields.Float(
        string=u"จำนวนเงินจากสลิป", digits=(16, 2), readonly=True, copy=False)
    scb_slip_sender = fields.Char(string=u"ชื่อผู้โอน (จากสลิป)", readonly=True, copy=False)
    scb_slip_sender_acc = fields.Char(string=u"บัญชีผู้โอน (จากสลิป)", readonly=True, copy=False)
    scb_slip_ref = fields.Char(string=u"เลขอ้างอิงจากสลิป", readonly=True, copy=False)
    scb_slip_raw = fields.Text(string=u"ข้อมูลดิบจาก AI", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # การตั้งค่า
    # ------------------------------------------------------------------
    @api.model
    def _scb_param(self, key):
        u"""อ่านค่าตั้งค่าจาก ir.config_parameter พร้อม fallback เป็นค่าเริ่มต้น"""
        default = DEFAULTS[key]
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'npd_scb_auto_payment.%s' % key)
        if raw in (None, False, ''):
            return default
        if isinstance(default, bool):
            return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')
        try:
            return type(default)(raw)
        except (ValueError, TypeError):
            return default

    @api.model
    def _scb_verify_start_date(self):
        u"""วันที่เริ่มตรวจสอบ — ยึด "วันที่ในใบรับชำระ"

        ใบรับชำระที่ลงวันที่ก่อนวันนี้ จะไม่ถูกดึงมาตรวจอัตโนมัติ (กันระบบไล่ย้อนหลัง
        ทั้งฐานข้อมูลจนเปลืองโควตา AI) แต่ยังกดปุ่ม "ตรวจสอบการโอน" เองได้
        คืน None = ไม่จำกัด (ตรวจทุกใบ)
        """
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'npd_scb_auto_payment.verify_start_date')
        if not raw:
            return None
        try:
            return fields.Date.to_date(str(raw)[:10])
        except (ValueError, TypeError):
            return None

    @api.depends('journal_id', 'payment_type', 'partner_type')
    def _compute_scb_verify_bank(self):
        u"""ธนาคารที่ใช้เทียบ — เลือกจาก "สมุดรายวัน" ของใบรับชำระ

        เงินค่าประกันเข้าคนละบัญชีกับค่าเช่า/ค่าอื่น ๆ จึงต้องดู statement คนละแท็บ
          • สมุดรายวันที่ชื่อมีคำว่า 'ค่าประกัน'  -> Statement_Kbank
          • สมุดรายวันอื่น                        -> statement_SCB
        (คำที่ใช้ตรวจและธนาคารปลายทางปรับได้ที่หน้าตั้งค่า)

        อ่านค่าตั้งค่าครั้งเดียวนอกลูป เพราะ compute ทำงานทีละหลายเรคคอร์ด
        """
        keyword = (self._scb_param('verify_deposit_journal_keyword') or '').strip()
        deposit_bank = self._scb_param('verify_bank_deposit')
        default_bank = self._scb_param('verify_bank_default')
        for payment in self:
            if payment.payment_type != 'inbound' or payment.partner_type != 'customer':
                payment.scb_verify_bank = False
                continue
            journal_name = payment.journal_id.name or ''
            payment.scb_verify_bank = (
                deposit_bank if (keyword and keyword in journal_name) else default_bank)

    def _scb_verify_sources(self):
        u"""แท็บ statement ที่ใช้เทียบกับใบรับชำระใบนี้"""
        self.ensure_one()
        return [self.scb_verify_bank] if self.scb_verify_bank else []

    # ------------------------------------------------------------------
    # เอกสารแนบ (สลิป)
    # ------------------------------------------------------------------
    def _scb_get_slip_attachments(self):
        u"""ไฟล์สลิปที่แนบกับใบรับชำระนี้ (ทั้งแนบตรง และแนบผ่าน chatter)"""
        self.ensure_one()
        attachments = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'account.payment'),
            ('res_id', '=', self.id),
        ])
        if self.message_ids:
            attachments |= self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'mail.message'),
                ('res_id', 'in', self.message_ids.ids),
            ])
        return attachments.filtered(lambda a: a.mimetype in SLIP_MIMETYPES and a.datas)

    # ------------------------------------------------------------------
    # เรียก Gemini (ตัวเดียวกับปุ่ม "ใช้วันที่จากสลิป")
    # ------------------------------------------------------------------
    def _scb_gemini_call(self, parts, max_tokens=1024):
        u"""ยิงคำขอไป Gemini แล้วคืน dict ที่ parse จาก JSON ที่ตอบกลับมา"""
        api_key = self._get_gemini_api_key()
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }
        url = "%s?key=%s" % (GEMINI_API_URL, api_key)
        try:
            response = requests.post(
                url, headers={"content-type": "application/json"},
                json=payload, timeout=90)
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.Timeout:
            raise UserError(_(u"เรียก Gemini API ไม่ทันเวลา (timeout) กรุณาลองใหม่"))
        except requests.exceptions.ConnectionError:
            raise UserError(_(u"เชื่อมต่อ Gemini API ไม่ได้ กรุณาตรวจสอบอินเทอร์เน็ต"))
        except requests.exceptions.HTTPError as e:
            msg = str(e)
            try:
                msg = e.response.json().get('error', {}).get('message', msg)
            except Exception:  # noqa: BLE001
                pass
            raise UserError(_(u"Gemini API Error: %s") % msg)
        except Exception as e:  # noqa: BLE001
            raise UserError(_(u"เรียก Gemini API ไม่สำเร็จ: %s") % e)

        for cand in result.get('candidates', []):
            for part in cand.get('content', {}).get('parts', []):
                text = part.get('text') or ''
                if not text:
                    continue
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    _logger.warning("SCB verify: Gemini ตอบไม่ใช่ JSON: %s", text[:500])
        return {}

    def _scb_slip_prompt(self):
        u"""คำสั่งให้ AI อ่านสลิป — ครอบคลุมสลิปหลายรูปแบบที่ลูกค้าใช้จริง

        รูปแบบที่ทดสอบแล้ว: SCB Payment Advice (ใบแจ้งการชำระเงิน), KBIZ,
        K PLUS (K+), Kept by krungsri, รายงาน IPP / INTERBANK TRANSFER ของกสิกร
        (ทั้งไฟล์ต้นฉบับและสแกนหมุน 90°), Bangkok Bank, ttb, LH Bank,
        MyMo by GSB, ธ.ก.ส. และรูปถ่ายจอมือถือ

        หลักคิดสำคัญ: ค่าที่อ่านได้จะถูกเอาไปเทียบกับ "รายการเดินบัญชีฝั่งผู้รับ"
        จึงต้องได้ (1) วันที่เงินเข้าบัญชีผู้รับ (2) ยอดที่เข้าบัญชีจริง
        (3) ชื่อผู้โอน — ไม่ใช่ชื่อผู้รับ
        """
        our_names = u''.join(
            u"     - %s\n" % n for n in self._get_company_name_candidates() if n)
        prompt = (
            u"คุณเป็นผู้เชี่ยวชาญอ่านสลิปโอนเงิน / ใบแจ้งการชำระเงิน (Payment Advice) / "
            u"รายงานการโอนเงินของธนาคาร ทั้งภาษาไทยและภาษาอังกฤษ\n"
            u"เอกสารอาจเป็นรูปถ่ายจอมือถือ (เอียง/สะท้อนแสง/จอแตก), ไฟล์สแกน, "
            u"หรือ PDF และ **อาจถูกหมุน 90 องศา** — ให้หมุนอ่านเองจนอ่านออก\n"
            u"อ่านแล้วตอบเป็น JSON เท่านั้น\n\n"

            u"########## 1) วันที่ ##########\n"
            u"ค่าที่ต้องการคือ **วันที่เงินเข้าบัญชีผู้รับ** เพราะจะเอาไปเทียบกับ\n"
            u"รายการเดินบัญชีของผู้รับ ไม่ใช่วันที่ผู้โอนกดโอน\n"
            u"ลำดับความสำคัญ:\n"
            u"  (ก) 'วันที่เงินเข้าบัญชี' / 'Received Date' / 'วันที่เงินถึงปลายทาง' / "
            u"'วันที่มีผล' / 'Value Date'  ← ใช้ก่อนเสมอถ้ามี\n"
            u"  (ข) 'วันที่ทำรายการ' / 'Transaction Date' / 'วันที่ทำรายการโอน'\n"
            u"  (ค) วันที่ใต้หัวข้อผลลัพธ์ เช่น 'โอนเงินสำเร็จ' / 'Transfer Completed' / "
            u"'ทำรายการสำเร็จ' / 'จ่ายบิลสำเร็จ' / 'รายการชำระบิลสำเร็จ' / 'สำเร็จ' / "
            u"'Transaction successful'\n"
            u"  (ง) 'วันที่หักบัญชี' / 'Deducted Date' — ใช้เป็นตัวสุดท้าย\n"
            u"**สำคัญ:** ถ้าเอกสารมีหลายวันที่ที่ไม่ตรงกัน (เช่นรายงาน IPP ที่ "
            u"'วันที่หักบัญชี 26-ก.ค.-2569' แต่ 'วันที่มีผล 27-ก.ค.-2569') "
            u"ให้ใส่ **ทุกวันที่ที่เป็นไปได้** ลงใน date_candidates โดยเรียง "
            u"วันที่เงินเข้าบัญชีผู้รับไว้ก่อน\n"
            u"ห้ามใช้: 'อัปเดตล่าสุด / Last Updated', 'วันที่พิมพ์', "
            u"'วันที่ - เวลา' ท้ายรายงาน, 'รายการมีผลตั้งแต่วันที่...ถึงวันที่' (ช่วงค้นหา)\n"
            u"ห้ามเอาตัวเลขจาก เวลา / เลขที่รายการ / จำนวนเงิน / เลขบัญชี "
            u"มาปนเป็นวัน-เดือน-ปีเด็ดขาด\n"
            u"แปลงเป็น DD/MM/YYYY (ค.ศ. 4 หลัก) เสมอ รองรับรูปแบบเหล่านี้:\n"
            u"  '27/07/2026' | '27 ก.ค. 2569' | '27 ก.ค. 69' | '27 ก.ค. 2026' |\n"
            u"  '25-ก.ค.-2569' | '25 Jul 26' | '13 Jun 26 11:45 AM' | "
            u"'24 ก.ค. 2569 08:44:43'\n"
            u"  - ตัดเวลาทิ้งเสมอ ('11:45 AM', '13.23 น.', ':44')\n"
            u"  - เดือนอังกฤษ (Jan..Dec) หรือไทย (ม.ค...ธ.ค. / มกราคม..ธันวาคม) -> 01-12\n"
            u"  - ปี 2 หลัก: ลอง 2000+YY ก่อน ถ้าเป็นอนาคตให้ตีเป็น พ.ศ. = (2500+YY)-543\n"
            u"    เช่น '69' -> 2569 พ.ศ. -> 2026 ค.ศ.  |  '26' -> 2026 ค.ศ.\n"
            u"  - ปี 4 หลัก >= 2500 เป็น พ.ศ. ให้ลบ 543 (2569 -> 2026)\n"
            u"  - ระวังสลิป ttb ที่เขียน 'เดือนไทย + ปี ค.ศ.' เช่น '27 ก.ค. 2026' "
            u"(ปีเป็น ค.ศ. อยู่แล้ว ห้ามลบ 543 ซ้ำ)\n\n"

            u"########## 2) จำนวนเงิน ##########\n"
            u"ค่าที่ต้องการคือ **ยอดที่เข้าบัญชีผู้รับจริง**\n"
            u"  - ปกติคือ 'จำนวนเงิน' / 'Amount' / 'จำนวนเงินทำรายการ' / "
            u"'จำนวนเงินรวมทั้งหมด' / 'ยอดรวมทั้งหมด' / 'Grand Total Amount'\n"
            u"  - **ค่าธรรมเนียมที่ผู้โอนเป็นคนจ่าย ไม่ต้องหักออกจากยอด** เช่น ttb "
            u"'ค่าธรรมเนียม (ผู้สั่งจ่าย) 10.00' -> ผู้รับได้เต็มจำนวน\n"
            u"  - ตอบเป็นตัวเลขล้วน ไม่มีคอมม่า ไม่มีสกุลเงิน เช่น 21550.00\n"
            u"  - ใส่ทุกยอดที่เป็นไปได้ลงใน amount_candidates (เรียงยอดที่มั่นใจสุดก่อน)\n"
            u"**ห้ามหยิบตัวเลขเหล่านี้มาเป็นจำนวนเงิน:**\n"
            u"  ค่าธรรมเนียม, ยอดคงเหลือ, ภาษีหัก ณ ที่จ่าย / ยอดภาษีที่ถูกหัก, "
            u"ยอดใบแจ้งหนี้ก่อน/หลัง VAT, อัตราภาษี, เลขบัญชี, เลขอ้างอิง, "
            u"เลข Biller ID / Tax ID, **ตัวเลขในโฆษณาท้ายสลิป** "
            u"(เช่น LH Bank มี 'ดอกเบี้ย 8.88% ต่อปี' — ไม่เกี่ยวกับรายการนี้)\n"
            u"รายงาน IPP / INTERBANK TRANSFER ของกสิกร: ให้ใช้คอลัมน์ 'จำนวนเงิน' "
            u"ของบรรทัดรายการ (= 'รวมจำนวนเงินทั้งหมด') ไม่ใช่ 'ยอดภาษีที่ถูกหัก', "
            u"'ค่าธรรมเนียมบริษัท', 'ยอดใบแจ้งหนี้ก่อน VAT' หรือ 'ยอดใบแจ้งนี้หลัง VAT'\n\n"

            u"########## 3) ชื่อผู้โอน (สำคัญที่สุด) ##########\n"
            u"ต้องเป็น **ผู้จ่ายเงิน** เท่านั้น อยู่ฝั่ง 'จาก' / 'From' / 'ผู้สั่งจ่าย' / "
            u"'รายละเอียดผู้จ่ายเงิน' / 'Sender Details' / 'บัญชีหักเงิน' / "
            u"'ชื่อบริษัท' (หัวรายงานของธนาคาร)\n"
            u"กฎเฉพาะที่มักอ่านผิด:\n"
            u"  • **SCB Payment Advice (ใบแจ้งการชำระเงิน)** มีชื่อบัญชี 2 ที่ ระวังสลับ!\n"
            u"      - 'เรียน ...' และ 'ชื่อบัญชี / Account Name' ใต้หัวธนาคาร = **ผู้รับ**\n"
            u"      - ผู้โอนอยู่ในกล่อง 'รายละเอียดผู้จ่ายเงิน / Sender Details' "
            u"และในประโยค 'ธนาคารได้โอนเงินจาก <ชื่อนี้> ให้กับท่าน'\n"
            u"  • **LH Bank / Kept / ttb** บรรทัดใต้ชื่อคนมักเป็น **ชื่อธนาคาร** "
            u"(เช่น 'แลนด์ แอนด์ เฮ้าส์', 'Krungsri', 'ไทยพาณิชย์') "
            u"ห้ามเอามาต่อท้ายชื่อผู้โอน ให้ใส่ในช่อง sender_bank แทน\n"
            u"  • **สลิปจ่ายบิล (Bill Payment / PromptPay / Biller ID)** ผู้โอนคือ "
            u"ชื่อบุคคลฝั่ง 'จาก' ส่วน 'REF001' / 'เลขที่อ้างอิง' ไม่ใช่ชื่อ\n"
            u"  • **รายงาน IPP หลายหน้า** ถ้าหน้านั้นไม่มีชื่อบริษัทผู้สั่งจ่าย "
            u"ให้ตั้ง sender_found = false (ห้ามเอาชื่อผู้รับมาตอบแทน)\n"
            u"  • ตอบชื่อเต็มตามที่เห็น ถ้ามีทั้งไทยและอังกฤษให้ใส่ทั้งคู่คั่นด้วย ' / '\n"
            u"    เช่น 'บจก.ทรัพย์ธารา ดีไซน์ แอนด์ คอนสตรัคชั่น / "
            u"SAPTHARA DESIGN&CONSTRUCTION CO.,LTD.'\n"
            u"  • ถ้าชื่อถูกตัดท้าย (เช่น 'นาย สุวรรณ ร') ให้ตอบตามที่เห็น ห้ามเดาต่อ\n\n"

            u"########## 4) ผู้รับเงิน / เลขบัญชี / เลขอ้างอิง ##########\n"
            u"  - ผู้รับ = ฝั่ง 'ไปยัง' / 'ถึง' / 'To' / 'ผู้รับเงิน' / "
            u"'ชื่อผู้รับเงิน' / 'เรียน'\n"
            u"  - เลขบัญชีตอบตามที่เห็น มาสก์ก็ได้ (เช่น 'xxx-x-x1838-x', "
            u"'XXX-XXX360-3', '037-7-xxx204')\n"
            u"  - เลขอ้างอิง = 'เลขที่รายการ' / 'Transaction ID' / 'รหัสอ้างอิง' / "
            u"'หมายเลขอ้างอิง' / 'รหัสทำรายการ' / 'เลขอ้างอิง'\n\n"
        )
        if our_names:
            prompt += (
                u"########## 5) บริษัทผู้รับเงิน (บริษัทของเรา) ##########\n"
                u"ชื่อต่อไปนี้คือ **ผู้รับเงิน** ห้ามตอบเป็น sender_name เด็ดขาด:\n"
                + our_names +
                u"  - ตั้ง recipient_matches_company = true ถ้าผู้รับในสลิปเป็นบริษัทนี้ "
                u"(ยอมรับคนละภาษา/สะกดต่าง/ชื่อถูกตัดท้าย เช่น 'NOPPADOL INTE')\n"
                u"  - ถ้าเผลออ่านชื่อนี้ไปอยู่ฝั่งผู้โอน แปลว่าอ่านสลับด้าน ให้กลับไปอ่านใหม่\n\n"
            )
        prompt += (
            u"########## รูปแบบคำตอบ (JSON เท่านั้น) ##########\n"
            u"{\n"
            u'  "found": true,\n'
            u'  "date": "DD/MM/YYYY",\n'
            u'  "date_candidates": ["DD/MM/YYYY"],\n'
            u'  "amount": 21550.00,\n'
            u'  "amount_candidates": [21550.00],\n'
            u'  "sender_name": "ชื่อผู้โอน (ไทย / อังกฤษ)",\n'
            u'  "sender_found": true,\n'
            u'  "sender_account": "เลขบัญชีผู้โอนตามที่เห็น",\n'
            u'  "sender_bank": "ชื่อธนาคารผู้โอน",\n'
            u'  "recipient_name": "ชื่อผู้รับเงิน",\n'
            u'  "recipient_account": "เลขบัญชีผู้รับ",\n'
            u'  "recipient_matches_company": true,\n'
            u'  "reference": "เลขอ้างอิง",\n'
            u'  "is_transfer_slip": true\n'
            u"}\n\n"
            u"ถ้าเอกสารไม่ใช่สลิป/หลักฐานการโอนเงิน ให้ตั้ง is_transfer_slip = false\n"
            u"ถ้าอ่านค่าใดไม่ได้ ให้ใส่ค่าว่าง \"\" หรือ 0 และตั้ง *_found = false "
            u"(ห้ามเดา ห้ามแต่งค่าขึ้นมาเอง)"
        )
        return prompt

    def _scb_slip_parts(self):
        u"""แปลงไฟล์แนบเป็น parts ของ Gemini (ใช้ทั้งรอบแรกและรอบสอง)"""
        self.ensure_one()
        parts = []
        for idx, att in enumerate(self._scb_get_slip_attachments(), 1):
            data = att.datas
            parts.append({"text": u"[ไฟล์ที่ %d] ชื่อไฟล์: %s" % (idx, att.name or '-')})
            parts.append({"inline_data": {
                "mime_type": att.mimetype or 'image/jpeg',
                "data": data.decode('utf-8') if isinstance(data, bytes) else data,
            }})
        return parts

    def _scb_read_slip(self):
        u"""ให้ AI อ่านสลิปที่แนบไว้ แล้วบันทึกค่าลงฟิลด์ scb_slip_* — คืน dict ผลลัพธ์"""
        self.ensure_one()
        attachments = self._scb_get_slip_attachments()
        if not attachments:
            # ยังไม่แนบสลิป = ยังตรวจไม่ได้ (ไม่ใช่ "ไม่สำเร็จ") ระบบจะกลับมาตรวจให้ใหม่
            # และไม่เสียโควตา AI เพราะยังไม่ได้ยิงไปเลย
            return {'error': _(
                u"ยังไม่ได้แนบสลิปการโอนเงินในเอกสารแนบ — กรุณาแนบไฟล์สลิป "
                u"(รูปภาพหรือ PDF) ที่หน้ารับชำระ แล้วระบบจะตรวจสอบให้อัตโนมัติ"),
                'retry': True, 'no_slip': True}

        parts = self._scb_slip_parts()
        parts.append({"text": self._scb_slip_prompt()})

        result = self._scb_gemini_call(parts, max_tokens=2048)
        if not result:
            return {'error': _(u"AI อ่านสลิปไม่สำเร็จ (ไม่ได้ข้อมูลกลับมา)")}
        if result.get('is_transfer_slip') is False:
            return {'error': _(u"ไฟล์ที่แนบไม่ใช่สลิป/หลักฐานการโอนเงิน")}

        date_str = (result.get('date') or '').strip()
        # ใช้ตัวแปลงวันที่ชุดเดียวกับปุ่ม "ใช้วันที่จากสลิป" (รองรับ พ.ศ./เดือนไทย)
        slip_date = self._parse_slip_date(date_str) if date_str else None

        amounts = []
        for val in [result.get('amount')] + list(result.get('amount_candidates') or []):
            amt = self._scb_to_float(val)
            if amt > 0 and amt not in amounts:
                amounts.append(amt)

        self.sudo().write({
            'scb_slip_read': True,
            'scb_slip_date': slip_date or False,
            'scb_slip_amount': amounts[0] if amounts else 0.0,
            'scb_slip_sender': (result.get('sender_name') or '').strip() or False,
            'scb_slip_sender_acc': (result.get('sender_account') or '').strip() or False,
            'scb_slip_ref': (result.get('reference') or '').strip() or False,
            'scb_slip_raw': json.dumps(result, ensure_ascii=False, indent=2),
        })
        return {'ok': True, 'date': slip_date, 'amounts': amounts, 'raw': result}

    def _scb_ai_same_company(self, slip_name, bank_names):
        u"""ถามความเห็น AI ว่า "ชื่อในสลิป" กับ "ชื่อในรายการธนาคาร" เป็นเจ้าเดียวกันไหม

        ใช้เป็นตัวช่วยเมื่อเทียบตัวอักษรแล้วไม่ผ่าน — เพราะธนาคารมักตัดชื่อให้สั้น
        และสลิปอาจเป็นคนละภาษากับที่ธนาคารบันทึก (ไทย/อังกฤษ)
        คืน index ของชื่อที่ตรง (int) หรือ None
        """
        names = [n for n in bank_names if n]
        if not slip_name or not names:
            return None
        listing = u''.join(u"  %d. %s\n" % (i, n) for i, n in enumerate(names))
        prompt = (
            u"เทียบว่า 'ชื่อในสลิปโอนเงิน' กับ 'ชื่อที่ธนาคารบันทึกไว้' เป็นบุคคล/บริษัท "
            u"เดียวกันหรือไม่\n\n"
            u"ชื่อในสลิป: %s\n\n"
            u"ชื่อที่ธนาคารบันทึกไว้ (เลือกได้อย่างมาก 1 ข้อ):\n%s\n"
            u"กฎ:\n"
            u"- ถือว่าเป็นเจ้าเดียวกันได้แม้เป็นคนละภาษา (ไทย/อังกฤษ) เช่น "
            u"'P.M.E.C METAL WORK CO.,LTD' = 'บจก. พี.เอ็ม.อี.ซี เมทัลเวิร์ค'\n"
            u"- ธนาคารมักตัดชื่อให้สั้น/ไม่ครบ ถ้าเป็นคำขึ้นต้นที่ตรงกันถือว่าเป็นเจ้าเดียวกัน\n"
            u"- มี/ไม่มีคำว่า บริษัท/หจก/จำกัด/CO.,LTD/(สำนักงานใหญ่) ไม่ทำให้ต่างกัน\n"
            u"- ถ้าไม่มีข้อใดตรงจริง ๆ ให้ตอบ match_index = -1 (ห้ามเดา)\n\n"
            u'ตอบ JSON: {"match_index": 0, "confident": true}'
        ) % (slip_name, listing)
        try:
            res = self._scb_gemini_call([{"text": prompt}], max_tokens=256)
        except UserError as e:
            _logger.warning("SCB verify: AI name match failed: %s", e)
            return None
        try:
            idx = int(res.get('match_index', -1))
        except (TypeError, ValueError):
            return None
        if 0 <= idx < len(names) and res.get('confident', True):
            return idx
        return None

    def _scb_second_opinion(self, dates, amounts, sources):
        u"""รอบสอง — ให้ AI ดู "รูปสลิป" คู่กับ "รายการเงินเข้าจริงในบัญชี" แล้วชี้เอง

        ใช้เมื่อรอบแรกจับคู่ไม่ได้ ซึ่งสาเหตุที่เจอบ่อยคือ
          • AI อ่านวันที่จากสลิปผิด (สลิปมีหลายวันที่ / รูปแบบ พ.ศ.-ค.ศ. ปนกัน)
          • ชื่อผู้โอนในสลิปกับที่ธนาคารบันทึกคนละภาษา หรือถูกตัดท้าย
        การส่งรายการจริงไปให้ดูพร้อมกัน ทำให้ AI เทียบได้ตรง ๆ แทนการเดา

        คืน dict {'statement': record, 'ai': dict} หรือ None
        """
        self.ensure_one()
        Statement = self.env['npd.scb.bank.statement'].sudo()
        window = self._scb_param('verify_second_pass_days')
        base = dates[0]

        rows = Statement.search([
            ('source', 'in', sources),
            ('deposit', '>', 0),
            ('date', '>=', base - timedelta(days=window)),
            ('date', '<=', base + timedelta(days=window)),
        ], order='date desc, time desc', limit=80)
        # รายการที่ "ยอดตรง" แต่หลุดนอกช่วงวัน — เผื่อกรณีอ่านวันที่ผิดไปไกล
        for amt in amounts:
            rows |= Statement.search([
                ('source', 'in', sources),
                ('deposit', '>=', amt - 0.01),
                ('deposit', '<=', amt + 0.01),
            ], order='date desc', limit=10)
        rows = rows.sorted(key=lambda r: (r.date or fields.Date.today(), r.time or ''),
                           reverse=True)
        if not rows:
            return None

        listing = u''.join(
            u"  %d. วันที่ %s %s | เงินเข้า %s | %s\n" % (
                i, r.date, r.time or '', '{:,.2f}'.format(r.deposit),
                r.description or u'(ธนาคารไม่ระบุรายละเอียด)')
            for i, r in enumerate(rows, 1))

        parts = self._scb_slip_parts()
        parts.append({"text": (
            u"งานนี้คือ **ตรวจทานรอบสอง** ระบบอ่านสลิปรอบแรกแล้วจับคู่กับบัญชีไม่ได้\n"
            u"สาเหตุที่พบบ่อยคือ อ่าน 'วันที่' ผิด หรือ 'ชื่อผู้โอน' เป็นคนละภาษากับ"
            u"ที่ธนาคารบันทึกไว้\n\n"
            u"ด้านบนคือรูป/ไฟล์สลิปการโอนเงิน\n"
            u"ด้านล่างคือ **รายการเงินเข้าจริงในบัญชีของผู้รับ** ที่ดึงมาจากธนาคาร:\n"
            u"%s\n"
            u"ให้ดูสลิปใหม่อย่างละเอียด แล้วตอบว่ารายการใดในลิสต์คือรายการเดียวกับสลิปนี้\n\n"
            u"เกณฑ์ตัดสิน (เรียงตามน้ำหนัก):\n"
            u"1. **จำนวนเงินต้องตรงกันเป๊ะ** — ถ้าไม่มีรายการไหนยอดตรง ให้ตอบ match_no = -1\n"
            u"   (อ่านยอดในสลิปใหม่ให้แน่ใจก่อน ระวังสับสนกับค่าธรรมเนียม/ภาษีหัก ณ ที่จ่าย/"
            u"ยอดคงเหลือ/ตัวเลขในโฆษณา)\n"
            u"2. **วันที่** ควรตรงกัน แต่คลาดกัน 1-2 วันได้ เพราะธนาคารอาจลงบัญชีข้ามวัน\n"
            u"   ถ้าวันที่ที่คุณอ่านได้ไม่ตรงกับรายการใดเลย ให้ย้อนอ่านวันที่ในสลิปใหม่ "
            u"— อาจอ่านสลับ พ.ศ./ค.ศ. หรือหยิบ 'วันที่พิมพ์/อัปเดตล่าสุด' มาผิด\n"
            u"3. **ชื่อผู้โอน** ให้เทียบแบบยืดหยุ่น ถือว่าตรงกันได้แม้:\n"
            u"   - คนละภาษา เช่น 'SAPTHARA DESIGN&CONSTRUCTION CO.,LTD.' = "
            u"'บจก. ทรัพย์ธารา ดีไซน์ แอนด์ คอนสตรัคชั่น'\n"
            u"   - ธนาคารตัดชื่อท้าย เช่น 'บจก. พี.เอ็ม.อี.ซี เม' = "
            u"'บจก. พี.เอ็ม.อี.ซี เมทัลเวิร์ค'\n"
            u"   - มี/ไม่มีคำว่า บริษัท/หจก/จำกัด/CO.,LTD\n"
            u"   - ธนาคารไม่ระบุชื่อเลย (จ่ายผ่านบิลเพย์เมนต์/เคาน์เตอร์เซอร์วิส) "
            u"— กรณีนี้ให้ตัดสินด้วยยอดเงินและวันที่แทน\n"
            u"4. ถ้ามีมากกว่า 1 รายการที่เข้าเกณฑ์เท่า ๆ กัน ให้ตอบ match_no = -1 "
            u"(ปลอดภัยกว่าเดาผิด)\n\n"
            u"ตอบ JSON เท่านั้น:\n"
            u"{\n"
            u'  "match_no": 3,\n'
            u'  "confident": true,\n'
            u'  "slip_date": "DD/MM/YYYY",\n'
            u'  "slip_amount": 21550.00,\n'
            u'  "slip_sender_name": "ชื่อผู้โอนที่อ่านได้จากสลิป",\n'
            u'  "reason": "อธิบายสั้น ๆ ว่าทำไมถึงเลือก/ไม่เลือก"\n'
            u"}\n"
            u"match_no = ลำดับในลิสต์ (1, 2, 3, ...) หรือ -1 ถ้าไม่มีรายการใดตรง"
        ) % listing})

        try:
            res = self._scb_gemini_call(parts, max_tokens=1024)
        except UserError as e:
            _logger.warning("SCB verify: second opinion failed: %s", e)
            return None
        if not res:
            return None
        try:
            no = int(res.get('match_no', -1))
        except (TypeError, ValueError):
            return None
        if not (1 <= no <= len(rows)) or not res.get('confident', True):
            return {'statement': None, 'ai': res}

        rec = rows[no - 1]
        # ป้องกัน AI ชี้มั่ว: ยอดของรายการที่เลือก ต้องตรงกับยอดที่อ่านได้จากสลิป
        # (ยอมรับทั้งยอดรอบแรกและยอดที่อ่านใหม่รอบสอง)
        tol = self._scb_param('verify_amount_tolerance')
        allowed = list(amounts)
        second_amt = self._scb_to_float(res.get('slip_amount'))
        if second_amt > 0:
            allowed.append(round(second_amt, 2))
        if not any(abs(rec.deposit - a) <= tol for a in allowed):
            _logger.info(
                "SCB verify: ปฏิเสธผลรอบสองของ payment %s — ยอดไม่ตรง "
                "(ธนาคาร %.2f / สลิป %s)", self.id, rec.deposit, allowed)
            return {'statement': None, 'ai': res}
        return {'statement': rec, 'ai': res}

    # ------------------------------------------------------------------
    # ตรรกะการตรวจสอบ
    # ------------------------------------------------------------------
    def _scb_verify_one(self, force_reread=False):
        u"""ตรวจสอบใบรับชำระ 1 ใบ -> เขียนผลลง scb_verify_* และคืน dict ผลลัพธ์"""
        self.ensure_one()
        Statement = self.env['npd.scb.bank.statement'].sudo()
        now = fields.Datetime.now()

        def finish(state, reason, statement=None):
            # เงินเข้าธนาคาร 1 รายการ ต้องผูกกับใบรับชำระได้ใบเดียวเท่านั้น
            # ถ้ามีใบอื่นจับคู่รายการนี้ไปแล้ว แปลว่าน่าจะบันทึกรับชำระซ้ำ
            if state == 'success' and statement:
                twin = self.sudo().search([
                    ('id', '!=', self.id),
                    ('scb_statement_id', '=', statement.id),
                    ('scb_verify_state', '=', 'success'),
                ], limit=1)
                if twin:
                    state = 'failed'
                    statement = None
                    reason = _(
                        u"รายการเงินเข้าของธนาคารรายการนี้ ถูกจับคู่กับใบรับชำระ "
                        u"%s ไปแล้ว\n"
                        u"เงินเข้า 1 รายการผูกได้กับใบรับชำระเดียวเท่านั้น — "
                        u"กรุณาตรวจสอบว่าบันทึกรับชำระซ้ำหรือไม่"
                    ) % (twin.display_name or twin.name or twin.id)
            vals = {
                'scb_verify_state': state,
                'scb_verify_reason': reason,
                'scb_verify_datetime': now,
                'scb_statement_id': statement.id if statement else False,
            }
            # นับเฉพาะครั้งที่ "ไม่สำเร็จ" เพื่อคุมจำนวนรอบที่ระบบจะลองซ้ำให้
            # (สถานะรออื่น ๆ ไม่นับ จะได้ตรวจซ้ำเรื่อย ๆ จนกว่าข้อมูลจะพร้อม)
            if state == 'failed':
                vals['scb_verify_attempts'] = (self.scb_verify_attempts or 0) + 1
            self.sudo().write(vals)
            return {'state': state, 'reason': reason}

        # ---- 0) ต้องลงบันทึกแล้วเท่านั้น ----
        # ใบร่างยังแก้จำนวนเงิน/วันที่/ลูกค้าได้อยู่ ถ้าตรวจตั้งแต่ตอนเป็นร่าง
        # ผลที่ได้จะใช้อ้างอิงไม่ได้ (แก้ทีหลังแล้วสถานะยังค้างว่า "โอนสำเร็จ")
        if self.state != 'posted':
            return finish('waiting', _(
                u"ใบรับชำระยังไม่ได้ลงบันทึก — ระบบจะเริ่มตรวจสอบการโอน "
                u"หลังกด \"ลงบันทึก\" แล้วเท่านั้น"))

        sources = self._scb_verify_sources()
        if not sources:
            return finish('waiting', _(
                u"ยังไม่ได้เลือกธนาคารที่จะตรวจสอบ — ตั้งค่าที่เมนู "
                u"ตรวจสอบการโอนเงิน > ตั้งค่า"))

        # ---- 1) อ่านสลิปด้วย AI (ใช้ค่าที่เคยอ่านไว้ ถ้ามี เพื่อไม่เปลืองโควตา) ----
        if force_reread or not self.scb_slip_read:
            try:
                read = self._scb_read_slip()
            except UserError as e:
                return finish('waiting', _(u"อ่านสลิปไม่สำเร็จ: %s") % e)
            if read.get('error'):
                if read.get('no_slip'):
                    return finish('no_slip', read['error'])
                # retry=True -> ยังตรวจไม่ได้ ให้กลับมาตรวจใหม่ได้ (ไม่ใช่ "ไม่สำเร็จ")
                return finish('waiting' if read.get('retry') else 'failed', read['error'])

        slip_sender = self.scb_slip_sender or ''
        raw = {}
        if self.scb_slip_raw:
            try:
                raw = json.loads(self.scb_slip_raw) or {}
            except (ValueError, TypeError):
                raw = {}

        amounts = []
        if self.scb_slip_amount:
            amounts.append(round(self.scb_slip_amount, 2))
        # ยอดสำรองจากสลิป (เช่น ยอดก่อน/หลังค่าธรรมเนียม) ที่ AI อ่านไว้
        for val in (raw.get('amount_candidates') or []):
            amt = self._scb_to_float(val)
            if amt > 0 and amt not in amounts:
                amounts.append(amt)

        # วันที่สำรองจากสลิป — สลิปโอนข้ามธนาคาร (IPP/SMART) มัก "วันที่หักบัญชี"
        # กับ "วันที่เงินเข้าบัญชี" คนละวัน จึงลองจับคู่ทุกวันที่ที่ AI อ่านได้
        dates = []
        if self.scb_slip_date:
            dates.append(self.scb_slip_date)
        for val in (raw.get('date_candidates') or []):
            d = self._parse_slip_date(str(val)) if val else None
            if d and d not in dates:
                dates.append(d)

        notes = []
        if not amounts:
            amounts = [round(abs(self.amount), 2)]
            notes.append(_(u"AI อ่านจำนวนเงินจากสลิปไม่ได้ — ใช้ยอดในใบรับชำระแทน"))
        if not dates:
            if not self.date:
                return finish('failed', _(
                    u"ไม่มีวันที่ให้ใช้ตรวจสอบ (ทั้งในสลิปและในใบรับชำระ)"))
            dates = [self.date]
            notes.append(_(u"AI อ่านวันที่จากสลิปไม่ได้ — ใช้วันที่ในใบรับชำระแทน"))
        elif self.date and dates[0] != self.date:
            notes.append(_(u"วันที่ในสลิป (%s) ไม่ตรงกับวันที่ในใบรับชำระ (%s)")
                         % (dates[0], self.date))
        if len(dates) > 1:
            notes.append(_(u"สลิปมีหลายวันที่ (%s) — ระบบลองจับคู่ให้ทุกวัน")
                         % u', '.join(str(d) for d in dates))
        slip_date = dates[0]

        # ---- 2) ยังไม่ถึงเวลาตรวจ (ข้อมูลธนาคารมาช้ากว่าจริง 1 วัน) ----
        # ใช้วันที่ล่าสุดในบรรดาวันที่ที่เป็นไปได้ เพื่อรอให้ข้อมูลของวันนั้นเข้ามาครบ
        lag = self._scb_param('verify_lag_days')
        today = fields.Date.context_today(self)
        ready_date = max(dates) + timedelta(days=lag)
        if today < ready_date:
            return finish('waiting', _(
                u"ข้อมูลการโอนของธนาคารมาช้ากว่าจริง %s วัน — "
                u"รายการวันที่ %s จะตรวจสอบได้ตั้งแต่วันที่ %s"
            ) % (lag, max(dates), ready_date))

        # ---- 3) จับคู่กับรายการเดินบัญชีจริง (ลองทุกวันที่ที่เป็นไปได้) ----
        bank_labels = dict(Statement._fields['source'].selection)
        notes.append(_(u"เทียบกับ statement ของ %s (ตามสมุดรายวัน \"%s\")")
                     % (u'/'.join(bank_labels.get(s, s) for s in sources),
                        self.journal_id.name or '-'))
        names = [n for n in [slip_sender, self.partner_id.name] if n]
        match_kwargs = {
            'amount': amounts,
            'names': names,
            'sources': sources,
            'amount_tol': self._scb_param('verify_amount_tolerance'),
            'day_tol': self._scb_param('verify_date_tolerance'),
            'name_threshold': self._scb_param('verify_name_threshold'),
            'account_hint': self.scb_slip_sender_acc,
        }
        amount_label = u' / '.join('{:,.2f}'.format(a) for a in amounts)

        match = None
        for d in dates:
            result = Statement.find_incoming_match(date=d, **match_kwargs)
            if result['matched']:
                if d != dates[0]:
                    notes.append(_(u"จับคู่ได้ด้วยวันที่สำรองจากสลิป (%s)") % d)
                return finish('success', self._scb_success_reason(
                    result['statement'], amount_label, d, slip_sender, notes),
                    result['statement'])
            # เก็บผลที่ "มีข้อมูลให้ดูมากที่สุด" ไว้ใช้อธิบายเหตุผลตอนไม่ผ่าน
            if match is None or (result['amount_date_candidates']
                                 and not match['amount_date_candidates']):
                match, slip_date = result, d

        candidates = match['amount_date_candidates']

        # ---- 3.5) รอบสอง: ให้ AI ดูสลิปเทียบกับรายการในบัญชีโดยตรง ----
        # แก้ปัญหาที่เจอบ่อย: อ่านวันที่ผิด / ชื่อคนละภาษา — ถ้ารอบแรกไม่ผ่าน
        # ให้ AI กลับไปอ่านสลิปใหม่พร้อมเห็นรายการจริงประกอบ
        if self._scb_param('verify_second_pass'):
            second = self._scb_second_opinion(dates, amounts, sources)
            if second and second.get('statement'):
                rec = second['statement']
                ai = second.get('ai') or {}
                self._scb_apply_second_pass(ai)
                notes.append(_(
                    u"รอบแรกจับคู่ไม่ได้ — ยืนยันโดย AI รอบสอง (อ่านสลิปซ้ำพร้อมเทียบ"
                    u"รายการจริงในบัญชี): %s") % (ai.get('reason') or '-'))
                return finish('success', self._scb_success_reason(
                    rec, '{:,.2f}'.format(rec.deposit), rec.date,
                    self.scb_slip_sender or slip_sender, notes), rec)
            if second and (second.get('ai') or {}).get('reason'):
                notes.append(_(u"ตรวจซ้ำรอบสองแล้วยังไม่พบรายการที่ตรง: %s")
                             % second['ai']['reason'])

        # ไม่พบรายการที่ตรงยอด+วันที่
        if not candidates:
            if not match['has_data_for_date']:
                return finish('waiting', _(
                    u"ยังไม่มีข้อมูลเดินบัญชีของวันที่ %s ในระบบ "
                    u"(ธนาคารส่งข้อมูลช้ากว่าจริง) — ระบบจะตรวจให้อัตโนมัติอีกครั้ง"
                ) % slip_date + self._scb_notes_text(notes))
            reason = _(
                u"ไม่พบรายการเงินเข้าที่ตรงกับสลิป\n"
                u"• จำนวนเงินจากสลิป: %s\n"
                u"• วันที่: %s\n"
                u"• ผู้โอน: %s"
            ) % (amount_label, slip_date, slip_sender or '-')
            other = match['amount_candidates']
            if other:
                reason += _(u"\n\nพบรายการที่ยอดตรงกันแต่คนละวัน: %s") % u', '.join(
                    u'%s (%s)' % (r.date, r.description or '-') for r in other[:5])
            else:
                reason += _(u"\n\nไม่พบรายการเงินเข้ายอดนี้ในบัญชีเลย")
            return finish('failed', reason + self._scb_notes_text(notes))

        # พบรายการที่ตรงยอด+วันที่ แต่ชื่อไม่ผ่าน -> ให้ AI ช่วยเทียบข้ามภาษาอีกที
        named = candidates.filtered(lambda r: r.counterparty)
        if slip_sender and named and self._scb_param('verify_ai_name_fallback'):
            bank_names = [r.counterparty for r in named]
            idx = self._scb_ai_same_company(slip_sender, bank_names)
            if idx is not None:
                rec = named[idx]
                notes.append(_(u"ชื่อผู้โอนยืนยันโดย AI (เทียบข้ามภาษา/ชื่อถูกตัดท้าย)"))
                return finish('success', self._scb_success_reason(
                    rec, amount_label, slip_date, slip_sender, notes), rec)

        # ธนาคารไม่ระบุชื่อผู้โอน (เช่น จ่ายผ่านบิลเพย์เมนต์/CrossBank)
        unnamed = candidates.filtered(lambda r: not r.counterparty)
        if unnamed and self._scb_param('verify_allow_no_name'):
            if len(candidates) == 1:
                notes.append(_(
                    u"ธนาคารไม่ได้ระบุชื่อผู้โอนในรายการนี้ (เช่น ชำระผ่านบิลเพย์เมนต์) — "
                    u"ยืนยันด้วยจำนวนเงินและวันที่"))
                return finish('success', self._scb_success_reason(
                    candidates[0], amount_label, slip_date, slip_sender, notes),
                    candidates[0])
            return finish('failed', _(
                u"พบรายการเงินเข้า %s รายการที่ยอด %s วันที่ %s ตรงกัน "
                u"แต่ชื่อผู้โอนไม่ตรง/ธนาคารไม่ได้ระบุชื่อ จึงชี้ชัดไม่ได้ว่าเป็นรายการใด "
                u"— กรุณาตรวจสอบด้วยตนเอง\n"
                u"• ชื่อในสลิป: %s\n"
                u"• รายการที่พบ: %s"
            ) % (len(candidates), amount_label, slip_date, slip_sender or '-',
                 u' | '.join(r.description or '-' for r in candidates[:5]))
                + self._scb_notes_text(notes))

        bank_names_txt = u', '.join(
            u'"%s"' % (r.counterparty or r.description or '-') for r in candidates[:5])
        return finish('failed', _(
            u"ชื่อผู้โอนไม่ตรงกับรายการของธนาคาร\n"
            u"• ชื่อในสลิป: %s\n"
            u"• ชื่อในรายการธนาคาร: %s\n"
            u"• จำนวนเงิน %s และวันที่ %s ตรงกัน\n"
            u"(คะแนนความเหมือนสูงสุด %.2f ต่ำกว่าเกณฑ์ %.2f)"
        ) % (slip_sender or '-', bank_names_txt, amount_label, slip_date,
             match['score'], self._scb_param('verify_name_threshold'))
            + self._scb_notes_text(notes))

    def _scb_apply_second_pass(self, ai):
        u"""เขียนค่าที่ AI อ่านใหม่ในรอบสองทับของเดิม

        รอบสองได้เห็นรายการจริงในบัญชีประกอบ ค่าที่อ่านได้จึงน่าเชื่อถือกว่ารอบแรก
        (โดยเฉพาะ "วันที่" ที่รอบแรกมักอ่านผิดจากสลิปที่มีหลายวันที่)
        """
        self.ensure_one()
        vals = {}
        raw_date = (ai.get('slip_date') or '').strip() if ai.get('slip_date') else ''
        parsed = self._parse_slip_date(raw_date) if raw_date else None
        if parsed and parsed != self.scb_slip_date:
            vals['scb_slip_date'] = parsed
        amount = self._scb_to_float(ai.get('slip_amount'))
        if amount > 0 and round(amount, 2) != round(self.scb_slip_amount or 0.0, 2):
            vals['scb_slip_amount'] = round(amount, 2)
        sender = (ai.get('slip_sender_name') or '').strip()
        if sender and sender != (self.scb_slip_sender or ''):
            vals['scb_slip_sender'] = sender
        if vals:
            self.sudo().write(vals)

    @staticmethod
    def _scb_notes_text(notes):
        return (u"\n\nหมายเหตุ:\n" + u'\n'.join(u"• %s" % n for n in notes)) if notes else ''

    def _scb_success_reason(self, statement, amount_label, slip_date, sender, notes):
        return _(
            u"จับคู่กับรายการเงินเข้าของธนาคารได้\n"
            u"• ธนาคาร: %s  วันที่ %s %s\n"
            u"• เงินเข้า: %s\n"
            u"• รายละเอียดจากธนาคาร: %s\n"
            u"• ผู้โอนตามสลิป: %s"
        ) % (
            dict(statement._fields['source'].selection).get(statement.source, statement.source),
            statement.date, statement.time or '',
            '{:,.2f}'.format(statement.deposit),
            statement.description or '-',
            sender or '-',
        ) + self._scb_notes_text(notes)

    # ------------------------------------------------------------------
    # ปุ่ม / cron
    # ------------------------------------------------------------------
    def action_scb_verify_transfer(self):
        u"""ปุ่ม "ตรวจสอบการโอน" บนหน้ารับชำระ — อ่านสลิปแล้วจับคู่กับธนาคารทันที"""
        self.ensure_one()
        res = self._scb_verify_one(force_reread=self.env.context.get('scb_force_reread', False))
        state_label = dict(self._fields['scb_verify_state'].selection).get(res['state'])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _(u"ผลตรวจสอบการโอน: %s") % state_label,
                'message': res['reason'],
                'type': 'success' if res['state'] == 'success' else (
                    'warning' if res['state'] == 'waiting' else 'danger'),
                'sticky': res['state'] != 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_scb_verify_selected(self):
        u"""ตรวจสอบการโอนของใบที่ติ๊กเลือกไว้ (เรียกจากเมนู Action ของตาราง)

        อัปเดตสถานะ "บนใบเดิม" ไม่สร้างรายการใหม่ — กดซ้ำได้เรื่อย ๆ เพื่อดูสถานะ
        ล่าสุดหลังรายการเดินบัญชีถูก sync เข้ามาเพิ่ม
        ใช้ค่าที่ AI เคยอ่านจากสลิปไว้แล้ว (ไม่อ่านซ้ำ) จึงไม่เปลืองโควตา
        ถ้าต้องการให้ AI อ่านสลิปใหม่ ให้เปิดใบนั้นแล้วกด "ตรวจสอบการโอนใหม่"
        """
        labels = dict(self._fields['scb_verify_state'].selection)
        tally, skipped, errors = {}, 0, 0
        for payment in self:
            if (payment.payment_type != 'inbound'
                    or payment.partner_type != 'customer'
                    or payment.state != 'posted'):
                skipped += 1
                continue
            try:
                res = payment._scb_verify_one()
                tally[res['state']] = tally.get(res['state'], 0) + 1
            except Exception:  # noqa: BLE001 - ใบเดียวพังต้องไม่ล้มทั้งชุด
                _logger.exception("SCB verify: ตรวจใบรับชำระ id=%s ไม่สำเร็จ", payment.id)
                errors += 1

        parts = [u"%s %s ใบ" % (labels.get(k, k), v) for k, v in tally.items()]
        if skipped:
            parts.append(_(u"ข้าม %s ใบ (ไม่ใช่เงินรับจากลูกค้า หรือยังไม่ลงบันทึก)")
                         % skipped)
        if errors:
            parts.append(_(u"ผิดพลาด %s ใบ") % errors)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _(u"ตรวจสอบการโอนเรียบร้อย"),
                'message': u' · '.join(parts) or _(u"ไม่มีใบที่ตรวจได้"),
                'type': 'success' if not errors else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_scb_verify_transfer_again(self):
        u"""ตรวจใหม่ทั้งหมด — บังคับให้ AI อ่านสลิปซ้ำ (ใช้เมื่อเปลี่ยนไฟล์แนบ)

        รีเซ็ตตัวนับด้วย เพื่อให้ระบบกลับมาลองซ้ำอัตโนมัติได้อีกรอบ
        (กรณีที่เคยชนเพดานไปแล้ว)
        """
        self.ensure_one()
        self.sudo().write({'scb_verify_attempts': 0})
        return self.with_context(scb_force_reread=True).action_scb_verify_transfer()

    @api.model
    def _scb_pending_domain(self):
        u"""ใบรับชำระที่ถึงคิวตรวจสอบ (ยึด "วันที่ในใบรับชำระ" ทั้งขอบบนและขอบล่าง)

        - ต้อง "ลงบันทึก (posted)" แล้วเท่านั้น — ใบร่างยังแก้ยอด/วันที่ได้อยู่
          การตีตราว่าโอนสำเร็จตั้งแต่ตอนเป็นร่างจึงไม่มีความหมาย
        - ขอบล่าง = วันที่เริ่มตรวจสอบที่ตั้งไว้ (ไม่ไล่ย้อนหลังเกินจุดนี้)
        - ขอบบน   = วันนี้ - จำนวนวันที่ข้อมูลธนาคารมาช้า (โอนวันนี้ -> ตรวจพรุ่งนี้)

        สถานะที่เข้าคิว:
          • รอตรวจสอบ / ยังไม่แนบสลิป / รอข้อมูลจากธนาคาร -> ตรวจซ้ำเรื่อย ๆ
          • ไม่สำเร็จ -> ตรวจซ้ำจนครบเพดานที่ตั้งไว้ (รายการเดินบัญชีของวันนั้น
            อาจเข้ามาไม่ครบตอนตรวจรอบแรก) ครบแล้วหยุด รอให้คนตรวจเอง
          • โอนสำเร็จ -> ไม่ตรวจซ้ำอีก
        """
        lag = self._scb_param('verify_lag_days')
        cutoff = fields.Date.context_today(self) - timedelta(days=lag)
        domain = [
            ('payment_type', '=', 'inbound'),
            ('partner_type', '=', 'customer'),
            ('state', '=', 'posted'),
            ('date', '<=', cutoff),
        ]
        start = self._scb_verify_start_date()
        if start:
            domain.append(('date', '>=', start))
        domain += self._scb_state_domain()
        return domain

    @api.model
    def _scb_state_domain(self):
        u"""ส่วนของ domain ที่คัดตามสถานะการโอน (ใช้ร่วมกับหน้าตั้งค่า)"""
        pending = ('to_check', 'no_slip', 'waiting', False)
        retry = self._scb_param('verify_retry_failed')
        if retry > 0:
            return ['|',
                    ('scb_verify_state', 'in', pending),
                    '&', ('scb_verify_state', '=', 'failed'),
                         ('scb_verify_attempts', '<', retry)]
        return [('scb_verify_state', 'in', pending)]

    @api.model
    def _cron_scb_verify_transfers(self):
        u"""Scheduled Action: ตรวจสอบใบรับชำระที่ยังไม่ได้ตรวจ (ทีละชุด)"""
        if not self._scb_param('verify_enabled'):
            return
        limit = self._scb_param('verify_batch_limit')
        payments = self.sudo().search(self._scb_pending_domain(),
                                      order='date asc, id asc', limit=limit)
        _logger.info("SCB verify: เริ่มตรวจสอบ %s ใบรับชำระ", len(payments))
        for payment in payments:
            try:
                payment._scb_verify_one()
                self.env.cr.commit()
            except Exception as e:  # noqa: BLE001 - หนึ่งใบพังต้องไม่ล้มทั้ง cron
                self.env.cr.rollback()
                _logger.exception("SCB verify: ตรวจสอบใบรับชำระ id=%s ไม่สำเร็จ", payment.id)
                payment.sudo().write({
                    'scb_verify_state': 'waiting',
                    'scb_verify_reason': _(u"ตรวจสอบไม่สำเร็จ: %s") % e,
                    'scb_verify_datetime': fields.Datetime.now(),
                })
                self.env.cr.commit()

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------
    @staticmethod
    def _scb_to_float(value):
        if value in (None, '', False):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        s = re.sub(r'[^\d.\-]', '', str(value))
        try:
            return float(s) if s not in ('', '-', '.', '-.') else 0.0
        except (ValueError, TypeError):
            return 0.0

    def action_draft(self):
        u"""กลับเป็นร่าง = ต้องตรวจสอบการโอนใหม่"""
        res = super(AccountPayment, self).action_draft()
        self.sudo().write({
            'scb_verify_state': 'to_check',
            'scb_verify_reason': False,
            'scb_statement_id': False,
            'scb_verify_attempts': 0,
        })
        return res
