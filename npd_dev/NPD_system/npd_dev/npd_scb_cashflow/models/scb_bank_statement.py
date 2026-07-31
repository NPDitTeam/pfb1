# -*- coding: utf-8 -*-
u"""รายการเดินบัญชีธนาคาร (Bank Statement) ดึงจากแท็บ statement_* ของสเปรดชีตเดียวกัน

ต่างจาก ``npd.scb.cashflow`` (สรุปยอด "รายวัน") — โมเดลนี้เก็บ "รายรายการ" ที่เข้า/ออก
บัญชี ตามคอลัมน์ A..O ของแท็บ statement_SCB:

    A Account Number | B Account Name | C Account Type | D Currency Code | E Branch Code
    F Date | G Time | H Tr Code | I Tr Description | J Channel | K Cheque No.
    L Withdrawal | M Deposit | N Outstanding Balance | O Description

ใช้เป็น "ข้อมูลการโอนจริงจากธนาคาร" ให้โมดูล npd_scb_auto_payment เอาไปจับคู่กับสลิป
ที่พนักงานแนบไว้ในหน้ารับชำระ (account.payment)
"""
import hashlib
import logging
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

# ผังคอลัมน์ของแต่ละธนาคาร (ชื่อฟิลด์ -> ลำดับคอลัมน์ เริ่มที่ 0 = คอลัมน์ A)
# แต่ละธนาคาร export มาคนละรูปแบบ จึงต้องแม็ปแยกกัน
LAYOUT_SCB = {
    # statement_SCB : A..O
    # A เลขบัญชี | B ชื่อบัญชี | C ประเภทบัญชี | D สกุลเงิน | E รหัสสาขา |
    # F วันที่ | G เวลา | H Tr Code | I Tr Description | J Channel |
    # K เลขที่เช็ค | L Withdrawal | M Deposit | N ยอดคงเหลือ | O รายละเอียด
    'account_no': 0, 'account_name': 1, 'account_type': 2, 'currency_code': 3,
    'branch_code': 4, 'date': 5, 'time': 6, 'tr_code': 7, 'tr_description': 8,
    'channel': 9, 'cheque_no': 10, 'withdrawal': 11, 'deposit': 12,
    'balance': 13, 'description': 14,
}
LAYOUT_KBANK = {
    # Statement_Kbank : A..I (ไม่มีเลขบัญชี/ประเภทบัญชี/เช็ค)
    # A วันที่ | B เวลา | C รายการ | D ถอนเงิน | E ฝากเงิน |
    # F ยอดคงเหลือ | G ช่องทาง | H รายละเอียด | I บริษัท
    'date': 0, 'time': 1, 'tr_description': 2, 'withdrawal': 3, 'deposit': 4,
    'balance': 5, 'channel': 6, 'description': 7, 'account_name': 8,
}

# แท็บ statement ในสเปรดชีต — ชื่อแท็บ/ช่วงข้อมูลตั้งได้ที่หน้าตั้งค่า
# (ชื่อแท็บว่าง = ไม่ดึงธนาคารนั้น)
STATEMENT_BANKS = [
    {'code': 'scb', 'name': 'SCB', 'config_field': 'statement_sheet_scb',
     'range_field': 'statement_range', 'layout': LAYOUT_SCB, 'default_range': 'A2:O'},
    {'code': 'kbank', 'name': 'Kbank', 'config_field': 'statement_sheet_kbank',
     'range_field': 'statement_range_kbank', 'layout': LAYOUT_KBANK,
     'default_range': 'A2:I'},
    {'code': 'ktb', 'name': u'กรุงไทย', 'config_field': 'statement_sheet_ktb',
     'range_field': 'statement_range_ktb', 'layout': LAYOUT_SCB,
     'default_range': 'A2:O'},
]
STATEMENT_CODES = [b['code'] for b in STATEMENT_BANKS]

# คำนำหน้าในคอลัมน์ Description ของธนาคาร ที่ไม่ใช่ "ชื่อคู่ค้า"
# เช่น "รับโอนจาก KBANK x7400 บจก. พี.เอ็ม.อี.ซี เม" -> ต้องเหลือ "บจก. พี.เอ็ม.อี.ซี เม"
_DESC_PREFIX_WORDS = [
    u'รับชำระค่าสินค้าและบริการ', u'ชำระค่าสินค้าและบริการ', u'ค่าสินค้าและบริการ',
    u'รับโอนเงินจาก', u'รับโอนจาก', u'เงินโอนจาก', u'โอนเงินจาก', u'รับโอน',
    u'โอนไปยัง', u'โอนเงินไปยัง', u'โอนไป', u'ฝากเงินสด', u'ฝากเงิน',
    u'รับชำระเงิน', u'รับชำระ', u'ชำระเงิน', u'เงินเข้า', u'เงินโอน',
    u'transfer from', u'received from', u'deposit from', u'payment from',
    # Kbank ขึ้นต้นสั้น ๆ ว่า "จาก X5001 น.ส. ..." — ต้องอยู่ท้ายสุดของลิสต์
    # เพราะโค้ดไล่ตัดจากคำยาวไปสั้น (คำยาวที่มี "จาก" ต้องถูกตัดก่อน)
    u'จาก',
]

# ชื่อ/รหัสธนาคารที่มักติดมาในคอลัมน์ Description — ตัดทิ้งก่อนเทียบชื่อ
_BANK_WORDS = [
    u'KBANK', u'SCB', u'KTB', u'BBL', u'TTB', u'TMB', u'BAY', u'GSB', u'LHB',
    u'LH BANK', u'UOB', u'CIMB', u'TISCO', u'KKP', u'BAAC', u'ICBC', u'CITI',
    u'SCBT', u'CROSSBANK', u'CrossBank', u'PROMPTPAY', u'PromptPay',
    u'ธ.ก.ส.', u'กรุงไทย', u'กสิกรไทย', u'ไทยพาณิชย์', u'กรุงเทพ', u'กรุงศรี',
    u'ออมสิน', u'ทหารไทย', u'ธนชาต', u'ไทยเครดิต', u'แลนด์ แอนด์ เฮ้าส์',
]

# รายละเอียดที่เป็น "ช่องทาง" ไม่ใช่ชื่อคู่ค้า — ธนาคารไม่ได้ระบุว่าใครโอนมา
# (ฝากผ่านเคาน์เตอร์/ตู้ ATM/CDM/บิลเพย์เมนต์) ถือว่า "ไม่มีชื่อผู้โอน"
_GENERIC_DESC_PATTERNS = [
    u'counter service', u'counterservice', u'เคาน์เตอร์เซอร์วิส', u'เคาน์เตอร์',
    u'atm', u'cdm', u'adm', u'kiosk', u'บิลเพย์เมนต์', u'bill payment',
    u'billpayment', u'promptpay', u'พร้อมเพย์', u'cash deposit', u'เงินสด',
]

# คำ/รูปแบบทางกฎหมายที่ตัดทิ้งตอน normalize ชื่อบริษัท (เทียบเฉพาะ "แก่นชื่อ")
_COMPANY_STOPWORDS = {
    u'บริษัท', u'บมจ', u'บจก', u'บจ', u'หจก', u'หสน', u'จำกัด', u'จํากัด', u'มหาชน',
    u'ห้างหุ้นส่วนจำกัด', u'ห้างหุ้นส่วนจํากัด', u'ห้างหุ้นส่วน', u'ห้าง', u'ร้าน',
    u'นาย', u'นาง', u'นางสาว', u'น.ส.', u'ด.ช.', u'ด.ญ.',
    u'mr', u'mrs', u'miss', u'ms',
    u'co', u'ltd', u'company', u'limited', u'public', u'inc', u'corp',
    u'corporation', u'the', u'and', u'part', u'partnership',
    u'สำนักงานใหญ่', u'สำนักงานใหญ', u'สํานักงานใหญ่', u'สํานักงานใหญ',
    u'สนงใหญ่', u'สนงใหญ', u'สาขา', u'head', u'office', u'branch', u'hq',
}

# ความยาวขั้นต่ำ (หลัง normalize) ที่ยอมให้ตัดสินว่า "ชื่อธนาคารถูกตัดท้าย"
# แล้วถือว่าตรงกัน — กันชื่อสั้น ๆ อย่าง "นภดล" ไปแมตช์บริษัทพี่น้องกันเอง
_TRUNCATED_PREFIX_MIN = 6


class ScbBankStatement(models.Model):
    _name = 'npd.scb.bank.statement'
    _description = 'Bank Statement Line (from Google Sheet)'
    _order = 'date desc, time desc, id desc'
    _rec_name = 'description'

    source = fields.Selection(
        selection=[(b['code'], b['name']) for b in STATEMENT_BANKS],
        string=u'ธนาคาร (แท็บ)', index=True, required=True)

    account_no = fields.Char(u'เลขบัญชี', index=True)          # A
    account_name = fields.Char(u'ชื่อบัญชี')                    # B
    account_type = fields.Char(u'ประเภทบัญชี')                  # C
    currency_code = fields.Char(u'สกุลเงิน')                    # D
    branch_code = fields.Char(u'รหัสสาขา')                      # E
    date = fields.Date(u'วันที่', index=True)                    # F
    time = fields.Char(u'เวลา')                                 # G
    tr_code = fields.Char(u'รหัสรายการ')                        # H
    tr_description = fields.Char(u'ประเภทรายการ')               # I
    channel = fields.Char(u'ช่องทาง')                           # J
    cheque_no = fields.Char(u'เลขที่เช็ค')                      # K
    withdrawal = fields.Monetary(u'เงินออก', currency_field='currency_id')   # L
    deposit = fields.Monetary(u'เงินเข้า', currency_field='currency_id')     # M
    balance = fields.Monetary(u'ยอดคงเหลือ', currency_field='currency_id')   # N
    description = fields.Char(u'รายละเอียด', index=True)        # O

    counterparty = fields.Char(
        u'ชื่อคู่ค้า (สกัดจากรายละเอียด)', readonly=True, index=True,
        help=u'ชื่อผู้โอน/ผู้รับที่สกัดจากคอลัมน์ Description โดยตัดคำนำหน้า '
             u'(รับโอนจาก / ชื่อธนาคาร / เลขบัญชีย่อ) ออกแล้ว')
    counterparty_acc = fields.Char(
        u'เลขบัญชีย่อคู่ค้า', readonly=True,
        help=u'เลขบัญชี 4 หลักท้ายที่ปรากฏในรายละเอียด เช่น x7400 -> 7400')

    row_key = fields.Char(u'คีย์แถว', index=True, required=True,
                          help=u'ลายนิ้วมือของแถวในชีต ใช้กันข้อมูลซ้ำตอน sync')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id.id)

    _sql_constraints = [
        ('row_key_source_uniq', 'unique(source, row_key)',
         u'รายการเดินบัญชีซ้ำ (source + row_key ต้องไม่ซ้ำกัน)'),
    ]

    # ------------------------------------------------------------------
    # ตัวช่วยแปลงค่าจากชีต
    # ------------------------------------------------------------------
    @staticmethod
    def _to_float(val):
        if val in (None, '', False):
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip().replace(',', '').replace(u'฿', '').replace(' ', '')
        if s in ('', '-'):
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_date(val):
        u"""รองรับ DD/MM/YYYY, DD/MM/YY, YYYY-MM-DD และปี พ.ศ. (>= 2500 -> ลบ 543)"""
        if val in (None, '', False):
            return False
        s = str(val).strip()
        if not s:
            return False
        for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y', '%d-%m-%y'):
            try:
                d = datetime.strptime(s, fmt).date()
            except ValueError:
                continue
            if d.year >= 2500:
                d = d.replace(year=d.year - 543)
            return d
        return False

    # ------------------------------------------------------------------
    # สกัด "ชื่อคู่ค้า" ออกจากคอลัมน์ Description ของธนาคาร
    # ------------------------------------------------------------------
    @api.model
    def _extract_counterparty(self, description):
        u"""ตัดคำนำหน้า/ชื่อธนาคาร/เลขบัญชีย่อ ออกจากรายละเอียด เหลือเฉพาะชื่อคู่ค้า

        "รับโอนจาก KBANK x7400 บจก. พี.เอ็ม.อี.ซี เม" -> ("บจก. พี.เอ็ม.อี.ซี เม", "7400")
        """
        text = (description or '').strip()
        if not text:
            return '', ''

        # เลขบัญชีย่อ เช่น x7400 / X7400 / xxx-x-x1838-x
        acc = ''
        m = re.search(r'[xX]{1,3}[-\s]?(\d{3,6})', text)
        if m:
            acc = m.group(1)
        # ลบรูปแบบเลขบัญชี/มาสก์ทั้งหมดทิ้ง
        text = re.sub(r'[xX]{1,}[-\s\d]*\d[-xX\d]*', ' ', text)

        # ตัดคำนำหน้า (เทียบแบบไม่สนตัวพิมพ์ ไล่จากคำยาวไปสั้น)
        low = text.lower()
        for word in sorted(_DESC_PREFIX_WORDS, key=len, reverse=True):
            w = word.lower()
            idx = low.find(w)
            if idx != -1:
                text = text[:idx] + ' ' + text[idx + len(word):]
                low = text.lower()

        # ตัดชื่อ/รหัสธนาคาร
        for word in sorted(_BANK_WORDS, key=len, reverse=True):
            text = re.sub(re.escape(word), ' ', text, flags=re.IGNORECASE)

        # Kbank ใส่ "++" ต่อท้ายเมื่อชื่อถูกตัด เช่น "น.ส. สุรีย์ลักษณ์ ++"
        text = re.sub(r'[+\s]+$', '', text)
        text = re.sub(r'\s+', ' ', text).strip(' -:/.,()')

        # เหลือแต่ชื่อช่องทาง (เคาน์เตอร์เซอร์วิส/ATM/บิลเพย์เมนต์) = ไม่มีชื่อผู้โอน
        probe = re.sub(r'[\d\s\-()./,]', '', text).lower()
        if not probe:
            return '', acc
        for pattern in _GENERIC_DESC_PATTERNS:
            if pattern.replace(' ', '') in probe:
                return '', acc
        return text, acc

    # ------------------------------------------------------------------
    # เปรียบเทียบชื่อบริษัท (ทนต่อชื่อที่ธนาคารตัดท้าย + ไทย/อังกฤษ)
    # ------------------------------------------------------------------
    @api.model
    def _normalize_name(self, name):
        u"""ย่อชื่อให้เหลือแก่นชื่อ: ตัดคำนำหน้า/รูปแบบทางกฎหมาย/วรรคตอน/ตัวเลข"""
        if not name:
            return ''
        s = name.lower()
        s = re.sub(r'[.,()\[\]{}\-_/\\&"\'`:;|+*]', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        tokens = [t for t in s.split(' ')
                  if t and t not in _COMPANY_STOPWORDS and not t.isdigit()]
        return ''.join(tokens)

    @api.model
    def _name_score(self, slip_name, bank_name):
        u"""คะแนนความเหมือน 0-1 ระหว่างชื่อจากสลิป กับชื่อจากรายการธนาคาร

        รายละเอียดของธนาคารมักถูก "ตัดท้าย" (เช่น "พี.เอ็ม.อี.ซี เม") จึงให้คะแนนเต็ม
        เมื่อชื่อฝั่งที่สั้นกว่าเป็น "คำขึ้นต้น" ของอีกฝั่ง และยาวพอที่จะระบุตัวตนได้
        """
        a = self._normalize_name(slip_name)
        b = self._normalize_name(bank_name)
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        # ธนาคารตัดชื่อท้าย -> ชื่อสั้นเป็นคำขึ้นต้นของชื่อยาว
        if len(shorter) >= _TRUNCATED_PREFIX_MIN and longer.startswith(shorter):
            return 1.0
        contain = (len(shorter) / float(len(longer))) if shorter in longer else 0.0
        return max(SequenceMatcher(None, a, b).ratio(), contain)

    # ------------------------------------------------------------------
    # ค้นหารายการเงินเข้าที่ตรงกับสลิป
    # ------------------------------------------------------------------
    @api.model
    def find_incoming_match(self, amount, date, names, sources=None,
                            amount_tol=0.0, day_tol=0, name_threshold=0.6,
                            account_hint=None):
        u"""หาแถว "เงินเข้า" ที่ตรงกับ จำนวนเงิน + วันที่ + ชื่อบริษัท

        :param amount: จำนวนเงินจากสลิป (หรือ list ของจำนวนเงินที่เป็นไปได้)
        :param date: วันที่ที่ใช้เทียบ (date object)
        :param names: list ชื่อผู้โอนที่ยอมรับได้ (จากสลิป / จากลูกค้าใน Odoo)
        :param sources: list รหัสธนาคารที่จะค้น (None = ทุกธนาคารที่ตั้งค่าไว้)
        :param amount_tol: ผลต่างจำนวนเงินที่ยอมรับ (0 = ต้องตรงเป๊ะระดับสตางค์)
        :param account_hint: เลขบัญชีผู้โอน (ใช้เทียบ 4 หลักท้ายเป็นสัญญาณเสริม)
        :return: dict {
            'matched': bool, 'statement': record|empty, 'score': float,
            'amount_date_candidates': recordset,   # ตรงยอด+วันที่ (ยังไม่เช็คชื่อ)
            'amount_candidates': recordset,        # ตรงยอดอย่างเดียว (คนละวัน)
            'has_data_for_date': bool,             # มีข้อมูลของวันนั้นในระบบแล้วหรือยัง
        }
        """
        amounts = amount if isinstance(amount, (list, tuple, set)) else [amount]
        amounts = [round(float(a), 2) for a in amounts if a]
        sources = [s for s in (sources or STATEMENT_CODES) if s in STATEMENT_CODES]
        empty = self.browse()
        result = {
            'matched': False, 'statement': empty, 'score': 0.0,
            'amount_date_candidates': empty, 'amount_candidates': empty,
            'has_data_for_date': False,
        }
        if not amounts or not date or not sources:
            return result

        date_from = date - timedelta(days=day_tol)
        date_to = date + timedelta(days=day_tol)
        result['has_data_for_date'] = bool(self.search_count([
            ('source', 'in', sources),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]))

        # ตรงยอด + อยู่ในช่วงวันที่
        amount_domain = ['|'] * (len(amounts) - 1)
        for amt in amounts:
            amount_domain += ['&', ('deposit', '>=', amt - amount_tol),
                              ('deposit', '<=', amt + amount_tol)]
        by_amount_date = self.search([
            ('source', 'in', sources),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ] + amount_domain)
        result['amount_date_candidates'] = by_amount_date

        # ตรงยอดอย่างเดียว (ไว้บอกผู้ใช้ว่าอาจลงวันผิด)
        result['amount_candidates'] = self.search(
            [('source', 'in', sources)] + amount_domain,
            order='date desc', limit=10)

        if not by_amount_date:
            return result

        hint = re.sub(r'\D', '', account_hint or '')[-4:] if account_hint else ''
        # ชื่อจากสลิปอาจมีทั้งไทยและอังกฤษคั่นด้วย " / " — แยกเทียบทีละท่อนด้วย
        # เพราะธนาคารบันทึกไว้ภาษาเดียว การเทียบทั้งก้อนจะไม่มีทางตรง
        clean_names = []
        for name in (names or []):
            for part in [name] + re.split(r'[/\r\n]+', str(name)):
                part = (part or '').strip()
                if part and part not in clean_names:
                    clean_names.append(part)

        best_rec, best_score = empty, 0.0
        for rec in by_amount_date:
            bank_names = [rec.counterparty, rec.description, rec.account_name]
            score = 0.0
            for sn in clean_names:
                for bn in bank_names:
                    score = max(score, self._name_score(sn, bn))
            # เลขบัญชี 4 หลักท้ายตรงกัน = สัญญาณยืนยันตัวตนที่หนักแน่น
            if hint and rec.counterparty_acc and rec.counterparty_acc[-4:] == hint:
                score = max(score, 1.0)
            if score > best_score:
                best_score, best_rec = score, rec

        result['score'] = best_score
        if best_score >= name_threshold:
            result['matched'] = True
            result['statement'] = best_rec
        return result

    # ------------------------------------------------------------------
    # ดึงข้อมูลจาก Google Sheet
    # ------------------------------------------------------------------
    @api.model
    def _row_to_vals(self, row, layout=None):
        u"""แปลง 1 แถวจากชีตเป็น dict ตาม "ผังคอลัมน์" ของธนาคารนั้น

        :param layout: dict ฟิลด์ -> ลำดับคอลัมน์ (ดู LAYOUT_SCB / LAYOUT_KBANK)
        """
        layout = layout or LAYOUT_SCB

        def text(field):
            i = layout.get(field)
            if i is None:
                return ''
            val = row[i] if i < len(row) else ''
            return '' if val is None else str(val).strip()

        def money(field):
            return self._to_float(text(field))

        date = self._parse_date(text('date'))
        description = text('description')
        counterparty, counterparty_acc = self._extract_counterparty(description)
        # คีย์แถวสร้างจาก "คอลัมน์ที่ระบุตัวรายการได้" เท่านั้น (ไม่รวมข้อความบรรยาย
        # ที่ธนาคารอาจตัด/จัดรูปแบบต่างกันในแต่ละครั้งที่ export) เพื่อไม่ให้เกิดแถวซ้ำ
        # ยอดคงเหลือสิ้นรายการทำให้แต่ละรายการไม่ซ้ำกันอยู่แล้ว
        raw = u'|'.join([
            text('account_no'),
            date.isoformat() if date else '',
            text('time'),
            text('tr_code'),
            '%.2f' % money('withdrawal'),
            '%.2f' % money('deposit'),
            '%.2f' % money('balance'),
        ])
        return {
            'account_no': text('account_no'),
            'account_name': text('account_name'),
            'account_type': text('account_type'),
            'currency_code': text('currency_code'),
            'branch_code': text('branch_code'),
            'date': date,
            'time': text('time'),
            'tr_code': text('tr_code'),
            'tr_description': text('tr_description'),
            'channel': text('channel'),
            'cheque_no': text('cheque_no'),
            'withdrawal': money('withdrawal'),
            'deposit': money('deposit'),
            'balance': money('balance'),
            'description': description,
            'counterparty': counterparty,
            'counterparty_acc': counterparty_acc,
            'row_key': hashlib.md5(raw.encode('utf-8')).hexdigest(),
        }

    @api.model
    def _friendly_sheet_error(self, error):
        u"""ย่อ error ก้อนโต ๆ ของ Google API ให้เหลือประโยคที่อ่านรู้เรื่อง"""
        raw = str(error)
        if 'RATE_LIMIT_EXCEEDED' in raw or 'Quota exceeded' in raw or '429' in raw[:40]:
            return _(u"Google จำกัดจำนวนคำขอ (เกิน 60 ครั้ง/นาที) — "
                     u"กดดึงข้อมูลถี่เกินไปหรือชนกับ Scheduled Action "
                     u"กรุณารอสัก 1 นาทีแล้วลองใหม่")
        if 'Unable to parse range' in raw:
            return _(u"ชื่อแท็บหรือช่วงข้อมูลไม่ถูกต้อง — "
                     u"ตรวจชื่อแท็บในสเปรดชีตให้ตรงกับที่ตั้งค่าไว้")
        if 'PERMISSION_DENIED' in raw or 'does not have permission' in raw:
            return _(u"Service Account ไม่มีสิทธิ์อ่านสเปรดชีตนี้ — "
                     u"แชร์ชีตให้อีเมล Service Account (สิทธิ์ Viewer) ก่อน")
        if 'NOT_FOUND' in raw or 'Requested entity was not found' in raw:
            return _(u"ไม่พบสเปรดชีตตาม Spreadsheet ID ที่ตั้งไว้")
        return raw[:300]

    @api.model
    def _sync_statements(self):
        u"""อ่านทุกแท็บ statement ที่ตั้งค่าไว้ แล้ว upsert -> คืนจำนวนแถวที่อ่านได้

        หมายเหตุ: ไม่ลบแถวเก่าที่หายจากชีต เพราะชีตเป็นหน้าต่างข้อมูลย้อนหลังจำกัด
        แต่ระบบต้องใช้ประวัติย้อนหลังในการตรวจสอบการโอน
        """
        Config = self.env['npd.scb.cashflow.config'].sudo()
        config = Config._get_config()
        service = Config._get_sheets_service(config)

        Model = self.sudo()
        total, created, errors, report = 0, 0, [], []

        # รวบรวมทุกแท็บที่ต้องอ่าน แล้วยิง Google เพียง "ครั้งเดียว" ด้วย batchGet
        # (เดิมยิงแยกทีละแท็บ ทำให้ชนลิมิต 60 read requests/นาที ได้ง่ายเมื่อ
        #  cron กับการกดปุ่มทำงานพร้อมกัน)
        jobs = []
        for bank in STATEMENT_BANKS:
            sheet_name = (getattr(config, bank['config_field'], '') or '').strip()
            if not sheet_name:
                # ข้ามแบบเงียบ ๆ ทำให้ผู้ใช้งงว่าทำไมไม่มีข้อมูล -> รายงานออกมาด้วย
                report.append(_(u"%s: ข้าม (ยังไม่ได้ตั้งชื่อแท็บในหน้าตั้งค่า)")
                              % bank['name'])
                continue
            data_range = (getattr(config, bank['range_field'], '')
                          or bank['default_range']).strip()
            jobs.append({
                'bank': bank,
                'sheet_name': sheet_name,
                'data_range': data_range,
                'range': u"'%s'!%s" % (sheet_name, data_range),
                'rows': [],
            })

        if jobs:
            try:
                resp = service.spreadsheets().values().batchGet(
                    spreadsheetId=config.spreadsheet_id,
                    ranges=[j['range'] for j in jobs]).execute()
                for job, value_range in zip(jobs, resp.get('valueRanges', [])):
                    job['rows'] = value_range.get('values', []) or []
            except Exception as e:  # noqa: BLE001 - ต้องรายงานให้อ่านรู้เรื่อง
                # ไม่ raise เพราะจะ rollback ทั้ง transaction แล้วข้อความ error
                # ที่เขียนลง config หายไปด้วย -> ผู้ใช้ไม่รู้ว่าพังเพราะอะไร
                message = self._friendly_sheet_error(e)
                report.append(_(u"ดึงข้อมูลจาก Google Sheet ไม่สำเร็จ — %s") % message)
                _logger.exception("Bank statement: batchGet failed")
                config.write({
                    'statement_last_sync': fields.Datetime.now(),
                    'statement_last_error': message,
                    'statement_last_result': '\n'.join(report),
                })
                return 0

        for job in jobs:
            bank = job['bank']
            sheet_name, data_range, rows = job['sheet_name'], job['data_range'], job['rows']
            existing = {r.row_key: r for r in Model.search([('source', '=', bank['code'])])}
            queued = set()   # คีย์ที่เพิ่งเจอในรอบนี้ (กันแถวซ้ำภายในชีตเดียวกัน)
            batch, read = [], 0
            for row in rows:
                vals = self._row_to_vals(row, bank['layout'])
                # แถวว่าง / ไม่มีวันที่ / ไม่มีทั้งเงินเข้าและเงินออก -> ข้าม
                if not vals['date'] or (not vals['deposit'] and not vals['withdrawal']):
                    continue
                total += 1
                read += 1
                if vals['row_key'] in queued:
                    continue
                rec = existing.get(vals['row_key'])
                if rec:
                    # แถวเดิม — อัปเดตเฉพาะเมื่อข้อความบรรยายจากธนาคารเปลี่ยนไป
                    if rec.description != vals['description']:
                        rec.write({
                            'description': vals['description'],
                            'counterparty': vals['counterparty'],
                            'counterparty_acc': vals['counterparty_acc'],
                            'tr_description': vals['tr_description'],
                            'channel': vals['channel'],
                        })
                    continue
                vals['source'] = bank['code']
                batch.append(vals)
                queued.add(vals['row_key'])
            if batch:
                Model.create(batch)
                created += len(batch)
            report.append(_(u"%s (%s %s): อ่านได้ %s แถว — ใหม่ %s แถว")
                          % (bank['name'], sheet_name, data_range, read, len(batch)))

        config.write({
            'statement_last_sync': fields.Datetime.now(),
            'statement_last_error': '\n'.join(errors) or False,
            'statement_last_result': '\n'.join(report) or False,
        })
        _logger.info("Bank statement: %s", ' | '.join(report))
        # ไม่ raise — ปล่อยให้ผลอยู่ในช่อง "ผลการดึงล่าสุด" ให้ผู้ใช้อ่านแทน
        # (raise จะ rollback ทำให้ข้อความที่เพิ่งเขียนหายไปด้วย)
        return created

    @api.model
    def action_refresh_statements(self):
        self._sync_statements()
        config = self.env['npd.scb.cashflow.config'].sudo()._get_config()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _(u'รายการเดินบัญชีธนาคาร'),
                'message': config.statement_last_result or _(u'ดึงข้อมูลเรียบร้อย'),
                'type': 'warning' if config.statement_last_error else 'success',
                'sticky': bool(config.statement_last_error),
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    @api.model
    def _cron_sync_statements(self):
        u"""เรียกจาก Scheduled Action"""
        config = self.env['npd.scb.cashflow.config'].sudo()._get_config()
        if not config.statement_auto_sync:
            return
        try:
            self._sync_statements()
        except Exception as e:  # noqa: BLE001 - cron ต้องไม่ล้ม
            _logger.error("Bank statement: cron sync failed: %s", e)
