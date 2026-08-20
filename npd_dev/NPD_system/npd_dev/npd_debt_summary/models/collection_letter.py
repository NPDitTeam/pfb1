# -*- coding: utf-8 -*-
"""ข้อมูลสำหรับรายงาน "ขอให้รีบชำระหนี้ค้างตามสัญญาเช่า"

รายงานนี้เป็นหนังสือทวงถามที่ออกจากหน้ารวมหนี้ลูกค้า เนื้อหาอ้างถึงสัญญาเช่า
ที่ลูกค้ายังค้างชำระ พร้อมตารางสรุปยอดหนี้ค้างชำระท้ายเอกสาร

การจับคู่ยอดในหนังสือกับแท็บบนหน้าจอ (ตกลงกับผู้ใช้ 19 ส.ค. 2026):
    1. ค่าเช่า                      = แท็บใบแจ้งหนี้ค่าเช่า
    2. ค่าเช่าเกินกำหนด             = แท็บค่าเช่าส่วนต่าง
    3. ค่าปรับเสียหายหรือสูญหาย     = แท็บค่าปรับหาย + แท็บค่าปรับชำรุด
    4. ค่าขนส่ง                     = แท็บค่าขนส่ง (ดึงข้ามมาจาก DB บริษัทขนส่ง)
    5. ค่าใช้จ่ายอื่นๆ               = แท็บใบแจ้งหนี้ค่าประกัน + แท็บค่าหัก ณ ที่จ่าย

เลขที่สัญญาเช่าดึงจาก sale.order.rental_contract_full (โมดูล
npd_rental_equipment_contract_qweb) ใบไหนหาสัญญาไม่เจอหรือสัญญาไม่มีเลข
จะไม่พิมพ์บรรทัดเลขที่สัญญาออกมา (ตามที่ผู้ใช้ระบุว่า "ถ้าไม่มี ซ่อน")
"""
import logging
from datetime import date

from odoo import models

_logger = logging.getLogger(__name__)

# บัญชีรับโอนของแต่ละบริษัท (แต่ละบริษัทอยู่คนละ DB) -- ชุดเดียวกับที่ใช้ใน
# ใบแจ้งหนี้/ใบวางบิลของ npd_debt_tracking_qweb
BANK_ACCOUNTS = {
    'NPD_S_Group_New': (u'บริษัท นภดล เอส กรุ๊ป จำกัด', u'186-222160-2'),
    'NPD_S_Group_New_V2': (u'บริษัท นภดล เอส กรุ๊ป จำกัด', u'186-222160-2'),
    'NPD_Steeltech_New': (u'บริษัท เอ็นพีดี สตีลเทค จำกัด', u'408-582058-4'),
    'NPD_Logistics_New': (u'บริษัท เอ็นพีดี โลจิสติกส์ จำกัด', u'439-044811-6'),
    'NPD_Intertrading_New': (u'บริษัท นภดล อินเตอร์เทรดดิ้ง จำกัด', u'408-546107-1'),
    'NPD_Bangkok_New': (u'บริษัท นภดล กรุงเทพ จำกัด', u'186-224773-9'),
}
BANK_NAME = u'ธนาคารไทยพาณิชย์'

THAI_MONTHS = [
    u'', u'มกราคม', u'กุมภาพันธ์', u'มีนาคม', u'เมษายน', u'พฤษภาคม', u'มิถุนายน',
    u'กรกฎาคม', u'สิงหาคม', u'กันยายน', u'ตุลาคม', u'พฤศจิกายน', u'ธันวาคม',
]


class NpdDebtSummaryLetter(models.Model):
    _inherit = 'npd.debt.summary'

    # ------------------------------------------------------------------
    # helper ทั่วไป
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

    def letter_bank_account(self):
        """ข้อความบัญชีรับโอนของบริษัทที่ออกหนังสือ (ดูจากชื่อ DB)

        เทียบชื่อ DB ตรงตัวก่อน ไม่ตรงค่อยเทียบแบบขึ้นต้น (เผื่อ DB ที่ copy
        ไปทดสอบ) ถ้ายังไม่เจอคืนค่าว่าง เทมเพลตจะพิมพ์จุดไข่ปลาให้เขียนมือแทน
        """
        dbname = self.env.cr.dbname or ''
        account = BANK_ACCOUNTS.get(dbname)
        if not account:
            for key in sorted(BANK_ACCOUNTS, key=len, reverse=True):
                if dbname.lower().startswith(key.lower()):
                    account = BANK_ACCOUNTS[key]
                    break
        if not account:
            return ''
        name, number = account
        return u'%s เลขที่บัญชี %s ชื่อบัญชี %s' % (BANK_NAME, number, name)

    def letter_baht_text(self, value):
        """จำนวนเงินเป็นตัวหนังสือ ใช้ helper เดิมของโมดูล"""
        return self._baht(value or 0.0)

    def _letter_sale_order(self, move):
        """หา sale.order ของใบแจ้งหนี้ 1 ใบ (คืน recordset ว่างถ้าไม่เจอ)

        ไล่หา 3 ทางตามลักษณะของเอกสารแต่ละแบบ
          1. ใบแจ้งหนี้ค่าเช่า/ส่วนต่าง : ผูกผ่านบรรทัดใบสั่งขายตรง ๆ
          2. ใบแจ้งหนี้ค่าประกัน       : ผูกผ่าน sale_order.rent_check (m2m)
          3. ใบเพิ่มหนี้ (ILS/IBK)     : ไม่ผูกกับบรรทัด ใช้ชื่อใน invoice_origin
        """
        if not move:
            return self.env['sale.order']
        order = move.invoice_line_ids.mapped('sale_line_ids.order_id')[:1]
        if order:
            return order
        SaleOrder = self.env['sale.order']
        if 'rent_check' in SaleOrder._fields:
            order = SaleOrder.search([('rent_check', 'in', move.id)], limit=1)
            if order:
                return order
        if move.invoice_origin:
            # invoice_origin อาจมีหลายเลขคั่นด้วยจุลภาค เอาตัวแรกที่หาเจอ
            for origin in move.invoice_origin.split(','):
                order = SaleOrder.search([('name', '=', origin.strip())], limit=1)
                if order:
                    return order
        return SaleOrder

    # ------------------------------------------------------------------
    # ข้อมูลหลักของรายงาน
    # ------------------------------------------------------------------
    def _letter_line_groups(self):
        """(ชื่อประเภทที่จะพิมพ์, บรรทัดของแท็บนั้น) เรียงตามลำดับแท็บบนหน้าจอ"""
        self.ensure_one()
        return [
            (u'ค่าเช่า', self.customer_invoice_line_ids),
            (u'ค่าประกัน', self.customer_deposit_line_ids),
            (u'ค่าเช่าเกินกำหนด', self.customer_rentdiff_line_ids),
            (u'ค่าปรับหาย', self.customer_penalty_line_ids),
            (u'ค่าปรับชำรุด', self.customer_damage_line_ids),
            (u'ค่าขนส่ง', self.customer_transport_line_ids),
            (u'ค่าหัก ณ ที่จ่าย', self.customer_tax_line_ids),
        ]

    def _letter_invoice_rows(self):
        """รวมทุกแท็บให้เป็นรายการเดียว เฉพาะใบที่ยังค้างชำระ

        คืน list ของ dict: doc_type / move / name / date / amount / order
        """
        self.ensure_one()
        rows = []
        for doc_type, lines in self._letter_line_groups():
            for line in lines:
                if line.payment_status != 'unpaid':
                    continue
                amount = getattr(line, 'amount_residual', 0.0)
                if not amount:
                    # แท็บค่าหัก ณ ที่จ่าย ใช้ชื่อฟิลด์ tax_amount
                    amount = getattr(line, 'tax_amount', 0.0)
                # บรรทัดค่าขนส่งมาจากอีก DB จึงไม่มี invoice_id ให้ไล่หา
                # ใช้เลขเอกสาร SO ต้นทางที่เก็บไว้หาสัญญาแทน
                move = getattr(line, 'invoice_id', False)
                if move:
                    order = self._letter_sale_order(move)
                else:
                    order = self.env['sale.order'].search(
                        [('name', '=', getattr(line, 'source_so', '') or '')], limit=1)
                rows.append({
                    'doc_type': doc_type,
                    'move': move,
                    'name': line.invoice_name or (move.name if move else ''),
                    'date': getattr(line, 'invoice_date', False)
                            or getattr(line, 'rental_start_date', False),
                    'amount': amount or 0.0,
                    'order': order,
                })
        return rows

    def get_collection_letter_data(self):
        """ข้อมูลทั้งหมดที่เทมเพลตต้องใช้ -- เรียกครั้งเดียวแล้ว t-set เก็บไว้"""
        self.ensure_one()
        rows = self._letter_invoice_rows()

        # จัดกลุ่มตามสัญญาเช่า (ใบที่หาสัญญาไม่เจอ รวมเป็นกลุ่มเดียวท้ายตาราง)
        groups = []
        index = {}
        for row in rows:
            order = row['order']
            key = order.id or 0
            if key not in index:
                contract_no = ''
                if order and 'rental_contract_full' in order._fields:
                    contract_no = order.rental_contract_full or ''
                index[key] = {
                    'contract_no': contract_no,
                    'contract_date': order.date_order.date() if order and order.date_order else False,
                    'order_name': order.name if order else '',
                    'invoices': [],
                    'amount': 0.0,
                }
                groups.append(index[key])
            group = index[key]
            group['invoices'].append(row)
            group['amount'] += row['amount']

        # เรียงตามวันที่ของสัญญา/ใบสั่งขาย (ไม่มีวันที่ไปท้ายสุด)
        # ใช้ลำดับเดียวกันทั้งช่องอ้างถึงและตารางสรุป เลขข้อจะได้ตรงกัน
        groups.sort(key=lambda g: (g['contract_date'] is False,
                                   g['contract_date'] or date.min,
                                   g['contract_no']))
        for seq, group in enumerate(groups, start=1):
            group['seq'] = seq

        penalty = (self.customer_penalty_residual or 0.0) + (self.customer_damage_residual or 0.0)
        other = (self.customer_deposit_residual or 0.0) + (self.customer_tax_residual or 0.0)
        amounts = {
            'rent': self.customer_amount_residual or 0.0,
            'over': self.customer_rentdiff_residual or 0.0,
            'penalty': penalty,
            'transport': self.customer_transport_residual or 0.0,
            'other': other,
            'total': self.grand_total or 0.0,
        }

        # ข้อ 1-5 ในหนังสือ: ตัดข้อที่ยอดเป็น 0 ออก แล้วเรียงเลขใหม่ให้ต่อกัน
        # (ผู้ใช้ระบุ 20 ส.ค. 2026 -- เดิมพิมพ์ครบทุกข้อรวมข้อที่เป็น 0)
        items = [
            (u'ค่าเช่า', amounts['rent']),
            (u'ค่าเช่าเกินกำหนด', amounts['over']),
            (u'ค่าปรับเสียหายหรือสูญหาย', amounts['penalty']),
            (u'ค่าขนส่ง', amounts['transport']),
            (u'ค่าใช้จ่ายอื่นๆ', amounts['other']),
        ]

        # อ้างถึง: 1 บรรทัดต่อ 1 สัญญา นับจำนวนใบแจ้งหนี้ในสัญญานั้น
        # ใบที่ยังไม่มีเลขที่สัญญาเช่าให้ใช้เลขใบสั่งขายแทน (เกณฑ์เดียวกับตารางสรุป)
        # ไม่งั้นลูกค้าที่ยังไม่ได้ออกเลขสัญญาจะได้หนังสือที่ช่องอ้างถึงว่างเปล่า
        refs = [g for g in groups if g['contract_no'] or g['order_name']]
        return {
            'groups': groups,
            'refs': refs,
            'amounts': amounts,
            'items': [{'label': label, 'amount': amount}
                      for label, amount in items if abs(amount) >= 0.005],
            'has_transport': bool(self.customer_transport_residual),
        }
