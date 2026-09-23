# -*- coding: utf-8 -*-
"""ชำระหนี้บ้านเขียว — ลูกหนี้เฉพาะบริษัทนี้ + ปรับยอดตามคำสั่งศาล

ดึงจากฐาน MySQL ชุดเดียวกับเมนู "สรุปลูกหนี้บ้านเขียวทั้งหมด" แต่กรองเฉพาะบิล
ที่ขึ้นต้นด้วยรหัสบริษัทของฐานนี้ จึงใช้ได้ทุก DB โดยไม่ต้องพึ่งข้อมูลข้ามฐาน
"""
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date
import logging
import pymysql

_logger = logging.getLogger(__name__)

# คำนำหน้าเลขใบกำกับเช่า -> บริษัทที่ออกบิล (ชุดเดียวกับ baankheaw.debtor_all_summary)
BILL_PREFIX_COMPANY = {
    'NSG': 'บริษัท นภดล เอส กรุ๊ป จำกัด',
    'NBK': 'บริษัท นภดล กรุงเทพ จำกัด',
    'NPI': 'บริษัท นภดล อินเตอร์เทรดดิ้ง จำกัด',
    'NST': 'บริษัท เอ็นพีดี สตีลเทค จำกัด',
}
DEFAULT_PREFIX = 'NSG'
# เดาบริษัทของฐานนี้จากชื่อบริษัทหลัก เมื่อยังไม่ได้ตั้งค่าพารามิเตอร์
COMPANY_NAME_HINT = [
    ('สตีลเทค', 'NST'),
    ('อินเตอร์เทรด', 'NPI'),
    ('กรุงเทพ', 'NBK'),
    ('เอส กรุ๊ป', 'NSG'),
    ('เอสกรุ๊ป', 'NSG'),
]
PREFIX_PARAM = 'baankheaw_debt_payment.prefix'

# ประเภทหนี้ 6 ช่อง (ลำดับตามคิวรีต้นฉบับ)
DEBT_TYPES = [
    ('b1', 'amount', 'ค่าเช่า'),
    ('b2', 'vat', 'Vat'),
    ('b3', 'tax', 'Tax'),
    ('b4', 'lost', 'ค่าปรับหาย'),
    ('b5', 'broken', 'ค่าปรับชำรุด'),
    ('b6', 'transport', 'ค่าขนส่ง'),
]
COURT_STATE_TEXT = 'ปรับตามศาลสั่ง'

DOC_PREFIX = u'NPD.B'


def _doc_number(seq, year_be):
    return u'%s %04d/%d' % (DOC_PREFIX, seq, year_be)


def _fmt(value):
    return '{:,.2f}'.format(value or 0.0)


DB_CONFIG = {
    'host': '150.95.26.61',
    'user': 'greenhome',
    'password': 'NPD@db789',
    'database': 'npd_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}

BILL_QUERY = """
SELECT
    f.cus_key,
    f.branch_key,
    COALESCE(c.cus_fullname, '')           AS cus_fullname,
    COALESCE(c.cus_cpnname, '')            AS cus_cpnname,
    COALESCE(c.cus_cpntel, '')             AS cus_cpntel,
    COALESCE(c.cus_address, '')            AS cus_address,
    COALESCE(c.cus_cpnadd, '')             AS cus_cpnadd,
    COALESCE(bm.branch_name, f.branch_key) AS branch_name,
    f.docid,
    f.doc_date,
    r.due_date,
    CASE
        WHEN r.has_open = 1 THEN 'ยังไม่ปิดบิล'
        WHEN r.has_open = 0 THEN 'ปิดบิล'
        ELSE 'ไม่มีข้อมูล'
    END AS bill_status,
    f.b1, f.b2, f.b3, f.b4, f.b5, f.b6, f.b_total
FROM (
    /* ===== ชั้น 4 : ต่อ 1 บิล -> ยอดคงค้างแยกตามประเภท ===== */
    SELECT
        u.cus_key,
        u.branch_key,
        u.docid,
        MIN(u.doc_date) AS doc_date,
        SUM(CASE WHEN u.type_seq = 1 THEN u.balance ELSE 0 END) AS b1,
        SUM(CASE WHEN u.type_seq = 2 THEN u.balance ELSE 0 END) AS b2,
        SUM(CASE WHEN u.type_seq = 3 THEN u.balance ELSE 0 END) AS b3,
        SUM(CASE WHEN u.type_seq = 4 THEN u.balance ELSE 0 END) AS b4,
        SUM(CASE WHEN u.type_seq = 5 THEN u.balance ELSE 0 END) AS b5,
        SUM(CASE WHEN u.type_seq = 6 THEN u.balance ELSE 0 END) AS b6,
        SUM(u.balance) AS b_total
    FROM (
        /* ===== ชั้น 3 : กรองเฉพาะที่ยังค้าง ===== */
        SELECT z.*
        FROM (
            /* ===== ชั้น 2 : unpivot 6 ประเภท ===== */
            SELECT
                m.cus_key,
                m.branch_key,
                m.docid,
                m.doc_date,
                t.type_seq,
                ROUND(
                    CASE t.type_seq
                        WHEN 1 THEN m.n_amount
                        WHEN 2 THEN m.n_vat
                        WHEN 3 THEN m.n_tax
                        WHEN 4 THEN m.n_lost
                        WHEN 5 THEN m.n_broken
                        WHEN 6 THEN m.n_transport
                    END
                , 2) AS balance
            FROM (
                /* ===== ชั้น 1 : ตั้งหนี้ - รับชำระ ต่อ 1 บิล ===== */
                SELECT
                    v.cus_key,
                    v.branch_key,
                    v.docid,
                    MIN(v.doc_date)  AS doc_date,
                    SUM(v.amount)    AS n_amount,
                    SUM(v.vat)       AS n_vat,
                    SUM(v.tax)       AS n_tax,
                    SUM(v.lost)      AS n_lost,
                    SUM(v.broken)    AS n_broken,
                    SUM(v.transport) AS n_transport
                FROM (
                    SELECT
                        TRIM(h.arh_cusid) AS cus_key,
                        TRIM(h.branchid)  AS branch_key,
                        COALESCE(NULLIF(TRIM(CONVERT(h.arh_docid USING utf8mb4)), ''),
                                 'ไม่ระบุเลขที่บิล') AS docid,
                        h.arh_date                   AS doc_date,
                        COALESCE(h.arh_amount, 0)    AS amount,
                        COALESCE(h.arh_vat, 0)       AS vat,
                        COALESCE(h.arh_tax, 0)       AS tax,
                        COALESCE(h.arh_lost, 0)      AS lost,
                        COALESCE(h.arh_broken, 0)    AS broken,
                        COALESCE(h.arh_transport, 0) AS transport
                    FROM npd_db.ar_head h
                    WHERE h.cancel = 'N'

                    UNION ALL

                    SELECT
                        TRIM(p.arp_cusid),
                        TRIM(p.branchid),
                        COALESCE(NULLIF(TRIM(CONVERT(p.arp_docid USING utf8mb4)), ''),
                                 'ไม่ระบุเลขที่บิล'),
                        NULL,
                        -COALESCE(p.arp_amount, 0),
                        -COALESCE(p.arp_vat, 0),
                        -COALESCE(p.arp_tax, 0),
                        -COALESCE(p.arp_lost, 0),
                        -COALESCE(p.arp_broken, 0),
                        -COALESCE(p.arp_transport, 0)
                    FROM npd_db.ar_repay p
                    WHERE p.cancel = 'N'
                ) v
                GROUP BY v.cus_key, v.branch_key, v.docid
            ) m
            CROSS JOIN (
                          SELECT 1 AS type_seq
                UNION ALL SELECT 2
                UNION ALL SELECT 3
                UNION ALL SELECT 4
                UNION ALL SELECT 5
                UNION ALL SELECT 6
            ) t
        ) z
        WHERE z.balance > 0.01
    ) u
    GROUP BY u.cus_key, u.branch_key, u.docid
) f
LEFT JOIN (
    /* pre-aggregate กัน renth_id ซ้ำ ไม่ให้ยอดถูกคูณ */
    SELECT
        TRIM(CONVERT(r.renth_id USING utf8mb4)) AS docid,
        MAX(COALESCE(r.renth_date_return, r.renth_dateend))   AS due_date,
        MAX(CASE WHEN r.renth_return = 'N' THEN 1 ELSE 0 END) AS has_open
    FROM npd_db.rentorder_head r
    GROUP BY TRIM(CONVERT(r.renth_id USING utf8mb4))
) r ON r.docid = f.docid
LEFT JOIN npd_db.master_customer c  ON TRIM(c.cus_id)     = f.cus_key
LEFT JOIN npd_db.master_branch   bm ON TRIM(bm.branch_id) = f.branch_key
ORDER BY branch_name, cus_fullname, f.docid
"""

INSURE_QUERY = """
SELECT
    w.cus_key,
    w.branch_key,
    ROUND(SUM(w.insure), 2) AS insure_balance,
    ROUND(SUM(w.paid), 2)   AS total_paid
FROM (
    SELECT TRIM(h.arh_cusid) AS cus_key, TRIM(h.branchid) AS branch_key,
           SUM(COALESCE(h.arh_insure, 0)) AS insure, 0 AS paid
    FROM npd_db.ar_head h WHERE h.cancel = 'N'
    GROUP BY TRIM(h.arh_cusid), TRIM(h.branchid)
    UNION ALL
    SELECT TRIM(p.arp_cusid), TRIM(p.branchid),
           -SUM(COALESCE(p.arp_insure, 0)),
           SUM(COALESCE(p.arp_amount,0) + COALESCE(p.arp_vat,0) + COALESCE(p.arp_tax,0)
             + COALESCE(p.arp_insure,0) + COALESCE(p.arp_lost,0) + COALESCE(p.arp_broken,0)
             + COALESCE(p.arp_transport,0))
    FROM npd_db.ar_repay p WHERE p.cancel = 'N'
    GROUP BY TRIM(p.arp_cusid), TRIM(p.branchid)
) w
GROUP BY w.cus_key, w.branch_key
"""

PRODUCT_QUERY = """
SELECT
    TRIM(CONVERT(d.rentd_id USING utf8mb4)) AS docid,
    d.rentd_proid                            AS product_code,
    d.rentd_proname                          AS product_name,
    SUM(COALESCE(d.rentd_amount, 0))         AS qty,
    SUM(COALESCE(d.rentd_amt_return, 0))     AS qty_return
FROM npd_db.rentorder_detail d
WHERE TRIM(CONVERT(d.rentd_id USING utf8mb4)) IN ({placeholders})
GROUP BY docid, d.rentd_proid, d.rentd_proname
ORDER BY docid, d.rentd_proid
"""


class BaankheawDebtPayment(models.Model):
    _name = 'baankheaw.debt_payment'
    _inherit = ['mail.thread']
    _description = 'ชำระหนี้บ้านเขียว'
    _order = 'branch_name, cus_fullname'
    _rec_name = 'cus_fullname'

    payment_state = fields.Selection([
        ('unpaid', 'ค้างชำระ'),
        ('paid', 'ชำระแล้ว'),
    ], string='สถานะการชำระ', default='unpaid', required=True, index=True,
        copy=False, tracking=True)

    doc_number = fields.Char(string='เลขที่เอกสาร', index=True, copy=False, readonly=True)

    # ===== ข้อมูลลูกค้า =====
    cus_id = fields.Char(string='รหัสลูกค้า', index=True)
    cus_fullname = fields.Char(string='ลูกค้า')
    cus_cpnname = fields.Char(string='บริษัทลูกค้า')
    cus_tel = fields.Char(string='เบอร์ติดต่อ')
    cus_address = fields.Char(string='ที่อยู่ลูกค้า')
    cus_cpnadd = fields.Char(string='ที่อยู่บริษัท')
    cus_cpntel = fields.Char(string='เบอร์บริษัท')
    branch_name = fields.Char(string='สาขา', index=True)
    bill_company_name = fields.Char(string='บริษัท', index=True,
                                    help='บริษัทที่ออกบิล อ่านจากคำนำหน้าเลขใบกำกับเช่า')

    # ===== ยอดเดิม =====
    amount = fields.Float(string='ค่าเช่า', digits=(16, 2))
    vat = fields.Float(string='Vat', digits=(16, 2))
    tax = fields.Float(string='Tax', digits=(16, 2))
    lost = fields.Float(string='ค่าปรับหาย', digits=(16, 2))
    broken = fields.Float(string='ค่าปรับชำรุด', digits=(16, 2))
    transport = fields.Float(string='ค่าขนส่ง', digits=(16, 2))
    total_debt = fields.Float(string='หนี้รวม', digits=(16, 2))

    insure_balance = fields.Float(string='ค่าประกันคงเหลือ', digits=(16, 2))
    total_paid = fields.Float(string='รับชำระ', digits=(16, 2))

    bill_count = fields.Integer(string='จำนวนบิลค้าง')
    bill_numbers = fields.Text(string='เลขใบกำกับเช่า')
    bill_ids = fields.One2many('baankheaw.debt_payment_bill', 'summary_id',
                               string='บิลค้างชำระ')

    date_start = fields.Date(string='วันที่เริ่มหนี้')
    due_date = fields.Date(string='วันที่ครบกำหนดชำระ')
    debt_duration = fields.Integer(string='ระยะเวลาที่เป็นหนี้ (วัน)')
    bill_status = fields.Char(string='สถานะบิล')

    # ===== ยอดใหม่ตามคำสั่งศาล (ไม่ทับยอดเดิม) =====
    court_amount = fields.Float(string='ค่าเช่า (ศาล)', digits=(16, 2), copy=False, tracking=True)
    court_vat = fields.Float(string='Vat (ศาล)', digits=(16, 2), copy=False, tracking=True)
    court_tax = fields.Float(string='Tax (ศาล)', digits=(16, 2), copy=False, tracking=True)
    court_lost = fields.Float(string='ค่าปรับหาย (ศาล)', digits=(16, 2), copy=False, tracking=True)
    court_broken = fields.Float(string='ค่าปรับชำรุด (ศาล)', digits=(16, 2), copy=False, tracking=True)
    court_transport = fields.Float(string='ค่าขนส่ง (ศาล)', digits=(16, 2), copy=False, tracking=True)

    court_amount_state = fields.Char(string='สถานะค่าเช่า', compute='_compute_court_states', store=True)
    court_vat_state = fields.Char(string='สถานะ Vat', compute='_compute_court_states', store=True)
    court_tax_state = fields.Char(string='สถานะ Tax', compute='_compute_court_states', store=True)
    court_lost_state = fields.Char(string='สถานะค่าปรับหาย', compute='_compute_court_states', store=True)
    court_broken_state = fields.Char(string='สถานะค่าปรับชำรุด', compute='_compute_court_states', store=True)
    court_transport_state = fields.Char(string='สถานะค่าขนส่ง', compute='_compute_court_states', store=True)

    court_total_debt = fields.Float(string='หนี้รวม (หลังศาลสั่ง)', digits=(16, 2),
                                    compute='_compute_court_states', store=True,
                                    help='ช่องไหนถูกปรับใช้ยอดศาล ช่องที่ไม่ได้ปรับใช้ยอดเดิม')
    is_court_adjusted = fields.Boolean(string='ปรับตามคำสั่งศาล', compute='_compute_court_states',
                                       store=True, index=True)
    court_adjust_date = fields.Datetime(string='วันที่ปรับยอด', readonly=True, copy=False)
    court_adjust_uid = fields.Many2one('res.users', string='ผู้ปรับยอด', readonly=True, copy=False)
    court_note = fields.Text(string='หมายเหตุคำสั่งศาล', copy=False)

    COURT_FIELDS = ['amount', 'vat', 'tax', 'lost', 'broken', 'transport']

    @api.depends('amount', 'vat', 'tax', 'lost', 'broken', 'transport',
                 'court_amount', 'court_vat', 'court_tax',
                 'court_lost', 'court_broken', 'court_transport')
    def _compute_court_states(self):
        """ช่องไหนกรอกยอดศาลไว้ ให้ขึ้นสถานะ 'ปรับตามศาลสั่ง' และใช้ยอดนั้นคิดหนี้รวม

        เทียบกับยอดเดิม ถ้าเท่ากันพอดีถือว่าไม่ได้ปรับ
        """
        for rec in self:
            total = 0.0
            adjusted = False
            for name in self.COURT_FIELDS:
                old_value = rec[name] or 0.0
                new_value = rec['court_%s' % name] or 0.0
                changed = abs(new_value - old_value) > 0.005
                rec['court_%s_state' % name] = COURT_STATE_TEXT if changed else ''
                total += new_value if changed else old_value
                adjusted = adjusted or changed
            rec.court_total_debt = total
            rec.is_court_adjusted = adjusted

    # ------------------------------------------------------------------
    # ปุ่ม
    # ------------------------------------------------------------------
    def action_mark_paid(self):
        self.write({'payment_state': 'paid'})
        return True

    def action_mark_unpaid(self):
        self.write({'payment_state': 'unpaid'})
        return True

    def action_open_court_wizard(self):
        """ปุ่ม 'เปลี่ยนยอดชำระจากศาล' — เปิดหน้าต่างกรอกยอดใหม่ทีละประเภท"""
        self.ensure_one()
        return {
            'name': 'เปลี่ยนยอดชำระจากศาล',
            'type': 'ir.actions.act_window',
            'res_model': 'baankheaw.debt_payment_court_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_summary_id': self.id},
        }

    def action_reset_court_amounts(self):
        """ยกเลิกการปรับยอด กลับไปใช้ยอดเดิมทั้งหมด"""
        self.write({
            'court_amount': 0.0, 'court_vat': 0.0, 'court_tax': 0.0,
            'court_lost': 0.0, 'court_broken': 0.0, 'court_transport': 0.0,
            'court_adjust_date': False, 'court_adjust_uid': False,
        })
        return True

    def action_fetch_data(self):
        """ปุ่มดึงข้อมูลใหม่ — ยอดที่ปรับตามศาลจะถูกเก็บไว้ ไม่หายไปกับการดึง"""
        self.env['baankheaw.debt_payment'].sudo().fetch_and_store()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ดึงข้อมูลลูกหนี้',
                'message': 'ดึงข้อมูลใหม่เรียบร้อย ยอดที่ปรับตามคำสั่งศาลถูกเก็บไว้เหมือนเดิม',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    # ------------------------------------------------------------------
    # บริษัทของฐานนี้
    # ------------------------------------------------------------------
    @api.model
    def _company_prefix(self):
        """รหัสบริษัทของฐานนี้ — อ่านจากพารามิเตอร์ ถ้าไม่ตั้งไว้ให้เดาจากชื่อบริษัทหลัก"""
        param = (self.env['ir.config_parameter'].sudo()
                 .get_param(PREFIX_PARAM) or '').strip().upper()
        if param in BILL_PREFIX_COMPANY:
            return param
        company_name = self.env.company.name or ''
        for keyword, prefix in COMPANY_NAME_HINT:
            if keyword in company_name:
                return prefix
        _logger.warning('baankheaw.debt_payment: เดาบริษัทจากชื่อ "%s" ไม่ได้ ใช้ %s',
                        company_name, DEFAULT_PREFIX)
        return DEFAULT_PREFIX

    @api.model
    def _belongs_here(self, doc_id, prefix):
        """บิลใบนี้เป็นของบริษัทนี้ไหม — เลขที่ไม่ตรงรหัสไหนเลยถือเป็น NSG"""
        code = (doc_id or '').strip()[:3].upper()
        if code not in BILL_PREFIX_COMPANY:
            code = DEFAULT_PREFIX
        return code == prefix

    # ------------------------------------------------------------------
    # ดึงข้อมูล
    # ------------------------------------------------------------------
    @api.model
    def _fetch_products(self, cursor, docids):
        """ดึงรายการสินค้าของบิลที่ยังค้าง แบ่งเป็นก้อนละ 500 กัน IN list ยาวเกิน"""
        products = {}
        docids = list(docids)
        for i in range(0, len(docids), 500):
            chunk = docids[i:i + 500]
            placeholders = ', '.join(['%s'] * len(chunk))
            cursor.execute(PRODUCT_QUERY.format(placeholders=placeholders), chunk)
            for row in cursor.fetchall():
                products.setdefault(row['docid'], []).append(row)
        return products

    @api.model
    def fetch_and_store(self):
        """ดึงข้อมูลลูกหนี้ของบริษัทนี้จากฐาน MySQL แล้วแทนที่ข้อมูลเดิม

        ยอดที่ปรับตามคำสั่งศาลและสถานะชำระแล้ว ถูกเก็บไว้แล้วนำกลับมาใส่หลังดึง
        โดยจับคู่ด้วย (รหัสลูกค้า, สาขา)
        """
        prefix = self._company_prefix()
        _logger.info('baankheaw.debt_payment: เริ่มดึงข้อมูลของบริษัท %s (%s)',
                     prefix, BILL_PREFIX_COMPANY.get(prefix, '-'))

        # เก็บของเดิมที่ต้องรักษาไว้
        keep = {}
        for rec in self.sudo().search([]):
            key = (rec.cus_id or '', rec.branch_name or '')
            keep[key] = {
                'payment_state': rec.payment_state,
                'court_amount': rec.court_amount, 'court_vat': rec.court_vat,
                'court_tax': rec.court_tax, 'court_lost': rec.court_lost,
                'court_broken': rec.court_broken, 'court_transport': rec.court_transport,
                'court_adjust_date': rec.court_adjust_date,
                'court_adjust_uid': rec.court_adjust_uid.id,
                'court_note': rec.court_note,
            }

        try:
            connection = pymysql.connect(**DB_CONFIG)
        except Exception as error:
            raise UserError('เชื่อมต่อฐานข้อมูลภายนอกไม่สำเร็จ: %s' % error)

        try:
            with connection.cursor() as cursor:
                cursor.execute(BILL_QUERY)
                all_rows = cursor.fetchall()
                bill_rows = [r for r in all_rows if self._belongs_here(r['docid'], prefix)]
                _logger.info('baankheaw.debt_payment: บิลทั้งหมด %s ใบ เป็นของบริษัทนี้ %s ใบ',
                             len(all_rows), len(bill_rows))

                cursor.execute(INSURE_QUERY)
                insure_map = {
                    (r['cus_key'], r['branch_key']): r for r in cursor.fetchall()
                }
                product_map = self._fetch_products(
                    cursor, {r['docid'] for r in bill_rows})
        finally:
            connection.close()

        summaries = {}
        for row in bill_rows:
            key = (row['cus_key'], row['branch_key'])
            summary = summaries.get(key)
            if not summary:
                summary = summaries[key] = {
                    'cus_id': row['cus_key'],
                    'cus_fullname': row['cus_fullname'],
                    'cus_cpnname': row['cus_cpnname'],
                    'cus_tel': row['cus_cpntel'],
                    'cus_cpntel': row['cus_cpntel'],
                    'cus_address': row['cus_address'],
                    'cus_cpnadd': row['cus_cpnadd'],
                    'branch_name': row['branch_name'],
                    'bill_company_name': BILL_PREFIX_COMPANY.get(prefix, ''),
                    'amount': 0.0, 'vat': 0.0, 'tax': 0.0,
                    'lost': 0.0, 'broken': 0.0, 'transport': 0.0,
                    'total_debt': 0.0, 'bill_count': 0,
                    'date_start': None, 'due_date': None,
                    'bill_ids': [], 'bill_texts': [], 'bill_numbers': [],
                    'bill_status': '',
                }

            values = {}
            for src_key, field_name, label in DEBT_TYPES:
                values[field_name] = float(row.get(src_key) or 0.0)
                summary[field_name] += values[field_name]
            bill_total = float(row.get('b_total') or 0.0)
            summary['total_debt'] += bill_total
            summary['bill_count'] += 1
            summary['bill_numbers'].append(row['docid'])

            doc_date = row.get('doc_date')
            bill_due = row.get('due_date')
            if doc_date and (not summary['date_start'] or doc_date < summary['date_start']):
                summary['date_start'] = doc_date
            if bill_due and (not summary['due_date'] or bill_due > summary['due_date']):
                summary['due_date'] = bill_due
            if row.get('bill_status') == 'ยังไม่ปิดบิล':
                summary['bill_status'] = 'ยังไม่ปิดบิล'
            elif not summary['bill_status']:
                summary['bill_status'] = row.get('bill_status') or ''

            detail_text = ' / '.join(
                '%s %s' % (label, _fmt(values[field_name]))
                for src_key, field_name, label in DEBT_TYPES
                if values[field_name] > 0.01
            )
            summary['bill_texts'].append('%s : %s' % (row['docid'], detail_text))

            product_vals = []
            product_texts = []
            for product in product_map.get(row['docid'], []):
                qty = float(product['qty'] or 0.0)
                qty_return = float(product['qty_return'] or 0.0)
                product_vals.append((0, 0, {
                    'doc_id': row['docid'],
                    'cus_fullname': row['cus_fullname'],
                    'branch_name': row['branch_name'],
                    'product_code': product['product_code'],
                    'product_name': product['product_name'],
                    'qty': qty,
                    'qty_return': qty_return,
                    'qty_outstanding': qty - qty_return,
                }))
                product_texts.append('%s (จำนวน: %s)' % (
                    product['product_name'] or product['product_code'] or '-', _fmt(qty)))

            summary['bill_ids'].append((0, 0, {
                'cus_id': row['cus_key'],
                'cus_fullname': row['cus_fullname'],
                'branch_name': row['branch_name'],
                'doc_id': row['docid'],
                'doc_date': doc_date,
                'due_date': bill_due,
                'bill_status': row['bill_status'],
                'amount': values['amount'],
                'vat': values['vat'],
                'tax': values['tax'],
                'lost': values['lost'],
                'broken': values['broken'],
                'transport': values['transport'],
                'total_debt': bill_total,
                'detail_text': detail_text,
                'product_summary': ', '.join(product_texts),
                'product_ids': product_vals,
            }))

        today = date.today()
        vals_list = []
        for key, summary in summaries.items():
            insure = insure_map.get(key) or {}
            summary['insure_balance'] = float(insure.get('insure_balance') or 0.0)
            summary['total_paid'] = float(insure.get('total_paid') or 0.0)
            summary['bill_numbers'] = ', '.join(summary['bill_numbers'])
            summary.pop('bill_texts', None)
            start = summary.get('date_start')
            summary['debt_duration'] = (today - start).days if start else 0
            vals_list.append(summary)

        self.sudo().search([]).unlink()

        created = self.sudo().browse()
        for i in range(0, len(vals_list), 100):
            created |= self.sudo().with_context(
                tracking_disable=True, mail_create_nolog=True
            ).create(vals_list[i:i + 100])

        # คืนค่าที่ต้องรักษาไว้
        restored = 0
        for rec in created:
            saved = keep.get((rec.cus_id or '', rec.branch_name or ''))
            if saved:
                rec.with_context(tracking_disable=True).write(saved)
                restored += 1

        self._assign_doc_numbers()
        _logger.info('baankheaw.debt_payment: สร้าง %s ราย / %s บิล (คืนค่าเดิม %s ราย)',
                     len(vals_list), len(bill_rows), restored)
        return True

    @api.model
    def _assign_doc_numbers(self):
        records = self.sudo().search([])
        if not records:
            return 0
        year_be = date.today().year + 543
        ordered = records.sorted(key=lambda r: (r.date_start or date.max, r.id))
        for seq, rec in enumerate(ordered, start=1):
            rec.doc_number = _doc_number(seq, year_be)
        return len(ordered)

    @api.model
    def load_once_on_install(self):
        """ดึงข้อมูลครั้งแรกตอนติดตั้ง — ถ้าต่อฐานภายนอกไม่ได้ ไม่ให้ติดตั้งล้ม"""
        if self.sudo().search_count([]):
            return True
        try:
            with self.env.cr.savepoint():
                return self.sudo().fetch_and_store()
        except Exception:
            _logger.exception('baankheaw.debt_payment: ดึงข้อมูลตอนติดตั้งไม่สำเร็จ '
                              'ให้กดปุ่มดึงข้อมูลใหม่จากเมนู')
            return False


class BaankheawDebtPaymentBill(models.Model):
    _name = 'baankheaw.debt_payment_bill'
    _description = 'บิลค้างชำระ (ชำระหนี้บ้านเขียว)'
    _order = 'doc_id'
    _rec_name = 'doc_id'

    summary_id = fields.Many2one('baankheaw.debt_payment', string='ลูกหนี้',
                                 required=True, ondelete='cascade', index=True)
    cus_id = fields.Char(string='รหัสลูกค้า')
    cus_fullname = fields.Char(string='ลูกค้า')
    branch_name = fields.Char(string='สาขา')

    doc_id = fields.Char(string='เลขใบกำกับเช่า', index=True)
    doc_date = fields.Date(string='วันที่บิล')
    due_date = fields.Date(string='วันที่ครบกำหนดชำระ')
    bill_status = fields.Char(string='สถานะบิล')

    amount = fields.Float(string='ค่าเช่า', digits=(16, 2))
    vat = fields.Float(string='Vat', digits=(16, 2))
    tax = fields.Float(string='Tax', digits=(16, 2))
    lost = fields.Float(string='ค่าปรับหาย', digits=(16, 2))
    broken = fields.Float(string='ค่าปรับชำรุด', digits=(16, 2))
    transport = fields.Float(string='ค่าขนส่ง', digits=(16, 2))
    total_debt = fields.Float(string='คงค้างรวม', digits=(16, 2))

    detail_text = fields.Char(string='รายละเอียดหนี้')
    product_summary = fields.Text(string='รายการสินค้า')
    product_ids = fields.One2many('baankheaw.debt_payment_product', 'bill_id',
                                  string='รายการสินค้าในบิล')


class BaankheawDebtPaymentProduct(models.Model):
    _name = 'baankheaw.debt_payment_product'
    _description = 'รายการสินค้าในบิล (ชำระหนี้บ้านเขียว)'
    _order = 'product_code'
    _rec_name = 'product_name'

    bill_id = fields.Many2one('baankheaw.debt_payment_bill', string='บิล',
                              required=True, ondelete='cascade', index=True)
    doc_id = fields.Char(string='เลขใบกำกับเช่า')
    cus_fullname = fields.Char(string='ลูกค้า')
    branch_name = fields.Char(string='สาขา')

    product_code = fields.Char(string='รหัสสินค้า')
    product_name = fields.Char(string='ชื่อสินค้า')
    qty = fields.Float(string='จำนวนที่เช่า', digits=(16, 2))
    qty_return = fields.Float(string='จำนวนที่คืน', digits=(16, 2))
    qty_outstanding = fields.Float(string='คงค้าง', digits=(16, 2))
