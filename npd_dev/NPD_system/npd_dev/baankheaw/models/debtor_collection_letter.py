# -*- coding: utf-8 -*-
"""หนังสือ "ขอให้รีบชำระหนี้ค้างตามสัญญาเช่า" ของลูกหนี้บ้านเขียว

รูปแบบเดียวกับหนังสือทวงถามของโมดูล npd_debt_summary
    หน้า 1 = ตัวหนังสือ / หน้า 2 = ตารางสรุปยอดหนี้ค้างชำระ

ต่างกันตรงที่มาของข้อมูล: ของบ้านเขียวไม่มีสัญญาเช่าใน Odoo ให้อ้างอิง
จึงอ้างถึง "ใบกำกับการเช่า" รายบิลจากแท็บบิลค้างชำระ (bill_ids) แทนสัญญา
ยอดในหนังสือจึงตรงกับที่เห็นบนหน้าจอเสมอ เพราะอ่านจากฟิลด์ชุดเดียวกัน

การจับคู่ยอดในหนังสือกับช่องบนหน้าจอ
    1. ค่าเช่า                    = ค่าเช่า
    2. ภาษีมูลค่าเพิ่ม            = Vat
    3. ภาษีหัก ณ ที่จ่าย          = Tax
    4. ค่าปรับเสียหายหรือสูญหาย   = ค่าปรับหาย + ค่าปรับชำรุด
    5. ค่าขนส่ง                   = ค่าขนส่ง
ข้อที่ยอดเป็น 0 จะถูกตัดออกแล้วเรียงเลขข้อใหม่ให้ต่อกัน (เหมือนหนังสือของ npd_debt_summary)
"""
import logging
from datetime import date

from odoo import models

try:
    from bahttext import bahttext
except ImportError:  # เครื่องที่ยังไม่ได้ติดตั้ง lib -- ให้พิมพ์เป็นตัวเลขแทน
    bahttext = None

_logger = logging.getLogger(__name__)

# บ้านเขียวอยู่ใน DB NPD_S_Group_New_V2 บัญชีรับโอนจึงใช้ของนภดล เอส กรุ๊ป
# (ชุดเดียวกับที่ใช้ในหนังสือทวงถามของ npd_debt_summary)
BANK_NAME = u'ธนาคารไทยพาณิชย์'
BANK_ACCOUNT_NAME = u'บริษัท นภดล เอส กรุ๊ป จำกัด'
BANK_ACCOUNT_NO = u'186-222160-2'

THAI_MONTHS = [
    u'', u'มกราคม', u'กุมภาพันธ์', u'มีนาคม', u'เมษายน', u'พฤษภาคม', u'มิถุนายน',
    u'กรกฎาคม', u'สิงหาคม', u'กันยายน', u'ตุลาคม', u'พฤศจิกายน', u'ธันวาคม',
]

# ข้อ 1-5 ในหนังสือ -> ฟิลด์ยอดหนี้ที่เอามารวมกัน
LETTER_ITEMS = [
    (u'ค่าเช่า', ('amount',)),
    (u'ภาษีมูลค่าเพิ่ม', ('vat',)),
    (u'ภาษีหัก ณ ที่จ่าย', ('tax',)),
    (u'ค่าปรับเสียหายหรือสูญหาย', ('lost', 'broken')),
    (u'ค่าขนส่ง', ('transport',)),
]

# ประเภทที่เอ่ยต่อท้ายหัวเรื่อง (ค่าเช่าเป็นฐานของหนังสืออยู่แล้ว ไม่ต้องเอ่ยซ้ำ)
TOPIC_ITEMS = [u'ค่าปรับเสียหายหรือสูญหาย', u'ค่าขนส่ง']

# ลูกค้าบางรายค้างหลายสิบบิล ถ้าไล่พิมพ์ในช่อง "อ้างถึง" หมดหน้าแรกจะล้น
# เกินจำนวนนี้จึงสรุปเป็นบรรทัดเดียวแล้วชี้ไปที่ตารางหน้า 2 แทน
MAX_REF_LINES = 10

# คำที่บอกว่าลูกค้าเป็นนิติบุคคล -> จ่าหน้าถึงกรรมการผู้มีอำนาจ
COMPANY_KEYWORDS = (u'บริษัท', u'จำกัด', u'ห้าง', u'หจก', u'หสม', u'มหาชน')


class DebtorAllSummaryLetter(models.Model):
    _inherit = 'baankheaw.debtor_all_summary'

    # ------------------------------------------------------------------
    # helper ที่เทมเพลตเรียกใช้
    # ------------------------------------------------------------------
    @staticmethod
    def letter_thai_date(value):
        """date -> '19 สิงหาคม 2569' (คืนค่าว่างถ้าไม่มีวันที่)"""
        if not value:
            return ''
        return u'%d %s %d' % (value.day, THAI_MONTHS[value.month], value.year + 543)

    @staticmethod
    def letter_amount(value):
        return '{:,.2f}'.format(value or 0.0)

    def letter_baht_text(self, value):
        """จำนวนเงินเป็นตัวหนังสือ"""
        if bahttext:
            return bahttext(value or 0.0)
        return '{:,.2f} บาท'.format(value or 0.0)

    def letter_bank_account(self):
        return u'%s เลขที่บัญชี %s ชื่อบัญชี %s' % (
            BANK_NAME, BANK_ACCOUNT_NO, BANK_ACCOUNT_NAME)

    def letter_addressee(self):
        """ชื่อผู้รับหนังสือ -- นิติบุคคลใช้ชื่อบริษัทและจ่าหน้าถึงกรรมการผู้มีอำนาจ

        ข้อมูลบ้านเขียวเก็บชื่อบริษัทไว้คนละช่องกับชื่อบุคคล และบางรายมีเครื่องหมาย
        กำกับสถานะไว้หน้าชื่อ เช่น *ฟ้องคดีแพ่ง* จึงตัดส่วนที่คร่อมด้วย * ออกก่อน
        """
        self.ensure_one()
        name = (self.cus_cpnname or '').strip()
        if name:
            while name.startswith('*') and name.count('*') >= 2:
                name = name[name.index('*', 1) + 1:].strip()
        if not name:
            return {'prefix': '', 'name': (self.cus_fullname or '').strip()}
        is_company = any(word in name for word in COMPANY_KEYWORDS)
        return {'prefix': u'กรรมการผู้มีอำนาจ ' if is_company else '', 'name': name}

    # ------------------------------------------------------------------
    # ข้อมูลหลักของรายงาน
    # ------------------------------------------------------------------
    def get_collection_letter_data(self):
        """ข้อมูลทั้งหมดที่เทมเพลตต้องใช้ -- เรียกครั้งเดียวแล้ว t-set เก็บไว้"""
        self.ensure_one()

        # เรียงบิลตามวันที่ (ไม่มีวันที่ไปท้ายสุด) ใช้ลำดับเดียวกันทั้งช่องอ้างถึง
        # และตารางสรุป เลขลำดับสองที่จะได้ตรงกัน
        bills = self.bill_ids.sorted(key=lambda b: (b.doc_date or date.max, b.doc_id or ''))
        rows = []
        for seq, bill in enumerate(bills, start=1):
            rows.append({
                'seq': seq,
                'doc_id': bill.doc_id or '',
                'doc_date': bill.doc_date or False,
                'due_date': bill.due_date or False,
                'detail': bill.detail_text or '',
                'status': bill.bill_status or '',
                'amount': bill.total_debt or 0.0,
            })

        amounts = {}
        for label, fields_ in LETTER_ITEMS:
            amounts[label] = sum(getattr(self, name) or 0.0 for name in fields_)
        total = self.total_debt or 0.0

        items = [{'label': label, 'amount': amounts[label]}
                 for label, _fields in LETTER_ITEMS
                 if abs(amounts[label]) >= 0.005]
        topics = [label for label in TOPIC_ITEMS if abs(amounts.get(label, 0.0)) >= 0.005]

        # อ้างถึง: บิลไม่เยอะก็ไล่ทีละบรรทัด เยอะเกินไปสรุปเป็นบรรทัดเดียว
        dates = [row['doc_date'] for row in rows if row['doc_date']]
        ref_summary = ''
        if len(rows) > MAX_REF_LINES:
            ref_summary = u'ใบกำกับการเช่า จำนวน %d ฉบับ' % len(rows)
            if dates:
                ref_summary += u' ตั้งแต่ฉบับลงวันที่ %s ถึงฉบับลงวันที่ %s' % (
                    self.letter_thai_date(min(dates)), self.letter_thai_date(max(dates)))
            ref_summary += u' รายละเอียดตามตารางสรุปยอดหนี้ค้างชำระ'

        return {
            'rows': rows,
            'refs': [] if ref_summary else rows,
            'ref_summary': ref_summary,
            'items': items,
            'amounts': amounts,
            'total': total,
            'topics': topics,
            'topics_text': (u' ' + u' '.join(topics)) if topics else u'',
            'addressee': self.letter_addressee(),
        }
