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

# ประเภทหนี้ 7 ช่อง เรียงตามเมนู "สรุปลูกหนี้ทั้งหมด" ซึ่งนับค่าประกันเป็นหนี้ด้วย
DEBT_TYPES = [
    ('n_amount', 'amount', 'ค่าเช่า'),
    ('n_vat', 'vat', 'Vat'),
    ('n_tax', 'tax', 'Tax'),
    ('n_insure', 'insure', 'ค่าประกัน'),
    ('n_lost', 'lost', 'ค่าปรับหาย'),
    ('n_broken', 'broken', 'ค่าปรับชำรุด'),
    ('n_transport', 'transport', 'ค่าขนส่ง'),
]
COURT_STATE_TEXT = 'ปรับตามศาลสั่ง'

DOC_PREFIX = u'NPD.B'


def _doc_number(seq, year_be):
    return u'%s %04d/%d' % (DOC_PREFIX, seq, year_be)


def _manual_doc_number(seq, year_be):
    """เลขของรายการที่สร้างเอง แยกซีรีส์ด้วย M กันชนกับเลขที่ไล่ใหม่ทุกครั้งที่ดึง"""
    return u'%s M%04d/%d' % (DOC_PREFIX, seq, year_be)


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

HEAD_QUERY = """
SELECT
    d.customer_id,
    d.branch_id,
    d.ลูกค้า AS cus_fullname,
    d.เบอร์ติดต่อ AS cus_tel,
    d.ที่อยู่ลูกค้า AS cus_address,
    d.บริษัท AS cus_cpnname,
    d.เบอร์บริษัท AS cus_cpntel,
    d.ที่อยู่บริษัท AS cus_cpnadd,
    d.สาขา AS branch_name,
    d.ค่าเช่า AS amount,
    d.Vat AS vat,
    d.tax AS tax,
    d.ค่าประกัน AS insure,
    d.ค่าปรับหาย AS lost,
    d.ค่าปรับชำรุด AS broken,
    d.ค่าขนส่ง AS transport,
    d.หนี้รวม AS total_debt,
    COALESCE(p.รับชำระ, 0) AS total_paid,
    d.หนี้รวม - COALESCE(p.รับชำระ, 0) AS remaining_balance,
    d.วันที่เริ่มหนี้ AS arh_date,
    d.วันที่ครบกำหนดชำระ AS due_date,
    DATEDIFF(CURDATE(), d.วันที่เริ่มหนี้) AS debt_duration,
    CASE
        WHEN DATEDIFF(CURDATE(), d.วันที่เริ่มหนี้) BETWEEN 0 AND 60 THEN 'สาขา & sales'
        WHEN DATEDIFF(CURDATE(), d.วันที่เริ่มหนี้) BETWEEN 61 AND 90 THEN 'ส่วนกลาง'
        WHEN DATEDIFF(CURDATE(), d.วันที่เริ่มหนี้) > 90
            AND (d.หนี้รวม - COALESCE(p.รับชำระ, 0)) >= 500000 THEN 'นิติกร'
        WHEN DATEDIFF(CURDATE(), d.วันที่เริ่มหนี้) > 90
            AND (d.หนี้รวม - COALESCE(p.รับชำระ, 0)) < 500000 THEN 'ส่วนกลาง'
        ELSE 'ไม่ระบุ'
    END AS responsible_party,
    CASE
        WHEN d.bill_status = 'N' THEN 'ยังไม่ปิดบิล'
        WHEN d.bill_status = 'Y' THEN 'ปิดบิล'
        ELSE 'ไม่มีข้อมูล'
    END AS bill_status_display
FROM
    (SELECT
        c.cus_id AS customer_id,
        c.cus_fullname AS ลูกค้า,
        c.cus_cpnname AS บริษัท,
        c.cus_tel AS เบอร์ติดต่อ,
        c.cus_address AS ที่อยู่ลูกค้า,
        c.cus_cpnadd AS ที่อยู่บริษัท,
        c.cus_cpntel AS เบอร์บริษัท,
        b.branch_name AS สาขา,
        b.branch_id AS branch_id,
        SUM(COALESCE(h.arh_amount, 0)) AS ค่าเช่า,
        SUM(COALESCE(h.arh_vat, 0)) AS Vat,
        SUM(COALESCE(h.arh_tax, 0)) AS tax,
        SUM(COALESCE(h.arh_insure, 0)) AS ค่าประกัน,
        SUM(COALESCE(h.arh_lost, 0)) AS ค่าปรับหาย,
        SUM(COALESCE(h.arh_broken, 0)) AS ค่าปรับชำรุด,
        SUM(COALESCE(h.arh_transport, 0)) AS ค่าขนส่ง,
        SUM(COALESCE(h.arh_amount,0) + COALESCE(h.arh_vat,0) +
            COALESCE(h.arh_tax,0) + COALESCE(h.arh_insure,0) +
            COALESCE(h.arh_lost,0) + COALESCE(h.arh_transport,0) +
            COALESCE(h.arh_broken,0)) AS หนี้รวม,
        MIN(h.arh_date) AS วันที่เริ่มหนี้,
        MAX(r.due_date) AS วันที่ครบกำหนดชำระ,
        CASE
            WHEN MAX(r.has_open) = 1 THEN 'N'
            WHEN MAX(r.has_open) = 0 THEN 'Y'
            ELSE NULL
        END AS bill_status
    FROM npd_db.ar_head h
    JOIN npd_db.master_customer c ON TRIM(h.arh_cusid) = TRIM(c.cus_id)
    JOIN npd_db.master_branch b ON TRIM(h.branchid) = TRIM(b.branch_id)
    /* pre-aggregate กัน renth_id ซ้ำ ไม่ให้ยอดตั้งหนี้ถูกคูณตามจำนวนแถวที่ join ติด */
    LEFT JOIN (
        SELECT TRIM(CONVERT(r0.renth_id USING utf8mb4)) AS renth_id,
               MAX(COALESCE(r0.renth_date_return, r0.renth_dateend))   AS due_date,
               MAX(CASE WHEN r0.renth_return = 'N' THEN 1 ELSE 0 END)  AS has_open
        FROM npd_db.rentorder_head r0
        GROUP BY TRIM(CONVERT(r0.renth_id USING utf8mb4))
    ) r ON TRIM(h.arh_docid) = r.renth_id
    WHERE h.cancel = 'N'
    GROUP BY c.cus_id, c.cus_fullname, c.cus_cpnname, c.cus_tel,
             c.cus_address, c.cus_cpnadd, b.branch_name, b.branch_id
    ) d
LEFT JOIN
    (SELECT
        c.cus_id AS customer_id,
        b.branch_id AS branch_id,
        SUM(COALESCE(p.arp_amount,0) + COALESCE(p.arp_vat,0) +
            COALESCE(p.arp_tax,0) + COALESCE(p.arp_insure,0) +
            COALESCE(p.arp_lost,0) + COALESCE(p.arp_broken,0) +
            COALESCE(p.arp_transport,0)) AS รับชำระ
    FROM npd_db.ar_repay p
    JOIN npd_db.master_customer c ON TRIM(p.arp_cusid) = TRIM(c.cus_id)
    JOIN npd_db.master_branch b ON TRIM(p.branchid) = TRIM(b.branch_id)
    WHERE p.cancel = 'N'
    GROUP BY c.cus_id, b.branch_id
    ) p ON d.customer_id = p.customer_id AND d.branch_id = p.branch_id
WHERE d.หนี้รวม - COALESCE(p.รับชำระ, 0) > 0
ORDER BY d.สาขา, d.ลูกค้า
"""

BILL_QUERY = """
SELECT
    f.cus_key,
    f.branch_key,
    f.docid,
    f.doc_date,
    r.due_date,
    CASE
        WHEN r.has_open = 1 THEN 'ยังไม่ปิดบิล'
        WHEN r.has_open = 0 THEN 'ปิดบิล'
        ELSE 'ไม่มีข้อมูล'
    END AS bill_status,
    f.n_amount, f.n_vat, f.n_tax, f.n_insure,
    f.n_lost, f.n_broken, f.n_transport, f.n_total
FROM (
    SELECT
        v.cus_key,
        v.branch_key,
        v.docid,
        MIN(v.doc_date) AS doc_date,
        ROUND(SUM(v.amount), 2)    AS n_amount,
        ROUND(SUM(v.vat), 2)       AS n_vat,
        ROUND(SUM(v.tax), 2)       AS n_tax,
        ROUND(SUM(v.insure), 2)    AS n_insure,
        ROUND(SUM(v.lost), 2)      AS n_lost,
        ROUND(SUM(v.broken), 2)    AS n_broken,
        ROUND(SUM(v.transport), 2) AS n_transport,
        ROUND(SUM(v.amount + v.vat + v.tax + v.insure +
                  v.lost + v.broken + v.transport), 2) AS n_total
    FROM (
        SELECT
            /* ยึดรหัสจากตารางหลัก ไม่ใช่รหัสที่พิมพ์ไว้ในบิล เพราะบางบิลพิมพ์ตัวเล็ก
               (17-c002853 vs 17-C002853) MySQL join ผ่านเพราะไม่สนตัวพิมพ์
               แต่ถ้าเอามาเป็นคีย์ตรง ๆ จะกลายเป็นลูกค้าคนละรายทันที */
            TRIM(c.cus_id)    AS cus_key,
            TRIM(b.branch_id) AS branch_key,
            COALESCE(NULLIF(TRIM(CONVERT(h.arh_docid USING utf8mb4)), ''),
                     'ไม่ระบุเลขที่บิล') AS docid,
            h.arh_date                   AS doc_date,
            COALESCE(h.arh_amount, 0)    AS amount,
            COALESCE(h.arh_vat, 0)       AS vat,
            COALESCE(h.arh_tax, 0)       AS tax,
            COALESCE(h.arh_insure, 0)    AS insure,
            COALESCE(h.arh_lost, 0)      AS lost,
            COALESCE(h.arh_broken, 0)    AS broken,
            COALESCE(h.arh_transport, 0) AS transport
        FROM npd_db.ar_head h
        JOIN npd_db.master_customer c ON TRIM(h.arh_cusid) = TRIM(c.cus_id)
        JOIN npd_db.master_branch   b ON TRIM(h.branchid)  = TRIM(b.branch_id)
        WHERE h.cancel = 'N'

        UNION ALL

        SELECT
            TRIM(c.cus_id),
            TRIM(b.branch_id),
            COALESCE(NULLIF(TRIM(CONVERT(p.arp_docid USING utf8mb4)), ''),
                     'ไม่ระบุเลขที่บิล'),
            NULL,
            -COALESCE(p.arp_amount, 0),
            -COALESCE(p.arp_vat, 0),
            -COALESCE(p.arp_tax, 0),
            -COALESCE(p.arp_insure, 0),
            -COALESCE(p.arp_lost, 0),
            -COALESCE(p.arp_broken, 0),
            -COALESCE(p.arp_transport, 0)
        FROM npd_db.ar_repay p
        JOIN npd_db.master_customer c ON TRIM(p.arp_cusid) = TRIM(c.cus_id)
        JOIN npd_db.master_branch   b ON TRIM(p.branchid)  = TRIM(b.branch_id)
        WHERE p.cancel = 'N'
    ) v
    GROUP BY v.cus_key, v.branch_key, v.docid
    HAVING ABS(SUM(v.amount)) > 0.005
        OR ABS(SUM(v.vat)) > 0.005
        OR ABS(SUM(v.tax)) > 0.005
        OR ABS(SUM(v.insure)) > 0.005
        OR ABS(SUM(v.lost)) > 0.005
        OR ABS(SUM(v.broken)) > 0.005
        OR ABS(SUM(v.transport)) > 0.005
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
ORDER BY f.cus_key, f.branch_key, f.docid
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

    is_manual = fields.Boolean(
        string='สร้างเอง', default=True, copy=False, readonly=True, index=True,
        help='รายการที่กดปุ่มสร้างเอง จะไม่ถูกลบตอนกดดึงข้อมูลลูกหนี้ '
             'ต่างจากรายการที่ดึงมาจากฐานบ้านเขียว ซึ่งถูกลบแล้วสร้างใหม่ทุกครั้งที่ดึง')

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

    responsible_party = fields.Char(string='ผู้รับผิดชอบ')

    # ===== ยอดค้างของบริษัทนี้ แยกตามประเภท (ตั้งหนี้ - รับชำระ) =====
    amount = fields.Float(string='ค่าเช่า', digits=(16, 2))
    vat = fields.Float(string='Vat', digits=(16, 2))
    tax = fields.Float(string='Tax', digits=(16, 2))
    insure = fields.Float(string='ค่าประกัน', digits=(16, 2))
    lost = fields.Float(string='ค่าปรับหาย', digits=(16, 2))
    broken = fields.Float(string='ค่าปรับชำรุด', digits=(16, 2))
    transport = fields.Float(string='ค่าขนส่ง', digits=(16, 2))
    total_debt = fields.Float(string='หนี้รวม', digits=(16, 2))

    # ===== ยอดของลูกหนี้รายนี้รวมทุกบริษัท (ตามสรุปลูกหนี้ทั้งหมด) =====
    customer_gross_debt = fields.Float(string='ตั้งหนี้รวม (ทุกบริษัท)', digits=(16, 2))
    customer_total_paid = fields.Float(string='รับชำระแล้ว (ทุกบริษัท)', digits=(16, 2))
    customer_remaining = fields.Float(string='ค้างชำระสุทธิ (ทุกบริษัท)', digits=(16, 2))

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
    court_insure = fields.Float(string='ค่าประกัน (ศาล)', digits=(16, 2), copy=False, tracking=True)
    court_lost = fields.Float(string='ค่าปรับหาย (ศาล)', digits=(16, 2), copy=False, tracking=True)
    court_broken = fields.Float(string='ค่าปรับชำรุด (ศาล)', digits=(16, 2), copy=False, tracking=True)
    court_transport = fields.Float(string='ค่าขนส่ง (ศาล)', digits=(16, 2), copy=False, tracking=True)

    # ธงบอกว่า "ศาลสั่งช่องนี้จริง" — จำเป็นเพราะยอดศาลเป็น 0 ได้
    # (ศาลสั่งยกยอดทิ้ง) ถ้าดูแค่ตัวเลขจะแยกไม่ออกจาก "ยังไม่เคยปรับ"
    court_amount_set = fields.Boolean(string='ศาลสั่งค่าเช่า', copy=False)
    court_vat_set = fields.Boolean(string='ศาลสั่ง Vat', copy=False)
    court_tax_set = fields.Boolean(string='ศาลสั่ง Tax', copy=False)
    court_insure_set = fields.Boolean(string='ศาลสั่งค่าประกัน', copy=False)
    court_lost_set = fields.Boolean(string='ศาลสั่งค่าปรับหาย', copy=False)
    court_broken_set = fields.Boolean(string='ศาลสั่งค่าปรับชำรุด', copy=False)
    court_transport_set = fields.Boolean(string='ศาลสั่งค่าขนส่ง', copy=False)

    court_amount_state = fields.Char(string='สถานะค่าเช่า', compute='_compute_court_states', store=True)
    court_vat_state = fields.Char(string='สถานะ Vat', compute='_compute_court_states', store=True)
    court_tax_state = fields.Char(string='สถานะ Tax', compute='_compute_court_states', store=True)
    court_insure_state = fields.Char(string='สถานะค่าประกัน', compute='_compute_court_states', store=True)
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

    COURT_FIELDS = ['amount', 'vat', 'tax', 'insure', 'lost', 'broken', 'transport']

    @api.depends('amount', 'vat', 'tax', 'insure', 'lost', 'broken', 'transport',
                 'court_amount', 'court_vat', 'court_tax', 'court_insure',
                 'court_lost', 'court_broken', 'court_transport',
                 'court_amount_set', 'court_vat_set', 'court_tax_set', 'court_insure_set',
                 'court_lost_set', 'court_broken_set', 'court_transport_set')
    def _compute_court_states(self):
        """ช่องไหนศาลสั่งไว้ ให้ขึ้นสถานะ 'ปรับตามศาลสั่ง' และใช้ยอดนั้นคิดหนี้รวม

        ยึดธง court_*_set ที่หน้าต่างปรับยอดเขียนไว้ ไม่ใช่เทียบตัวเลข เพราะ
        ศาลสั่งให้เป็น 0 ได้ ถ้าเทียบตัวเลขจะกลายเป็นว่าลูกหนี้ทุกรายที่ยังไม่
        เคยปรับ ถูกตีว่าศาลสั่งให้จ่าย 0 แล้วออกใบแจ้งหนี้ไม่ได้
        """
        for rec in self:
            total = 0.0
            adjusted = False
            for name in self.COURT_FIELDS:
                changed = bool(rec['court_%s_set' % name])
                rec['court_%s_state' % name] = COURT_STATE_TEXT if changed else ''
                total += (rec['court_%s' % name] or 0.0) if changed else (rec[name] or 0.0)
                adjusted = adjusted or changed
            rec.court_total_debt = total
            rec.is_court_adjusted = adjusted

    # ------------------------------------------------------------------
    # สร้างเอง
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """รายการที่สร้างเองต้องมีเลขที่เอกสารของตัวเอง

        เลขของรายการที่ดึงมาถูกไล่ใหม่หมดทุกครั้งที่ดึง (_assign_doc_numbers)
        จึงแยกซีรีส์ของรายการที่สร้างเองออกมา ไม่ให้ถูกไล่ทับหรือเลขชนกัน
        """
        records = super(BaankheawDebtPayment, self).create(vals_list)
        pending = records.filtered(lambda r: r.is_manual and not r.doc_number)
        if pending:
            year_be = date.today().year + 543
            seq = self._next_manual_seq()
            for rec in pending:
                rec.doc_number = _manual_doc_number(seq, year_be)
                seq += 1
        return records

    @api.model
    def _next_manual_seq(self):
        """เลขลำดับถัดไปของซีรีส์ที่สร้างเอง"""
        top = 0
        marker = '%s M' % DOC_PREFIX
        for rec in self.sudo().search([('is_manual', '=', True),
                                       ('doc_number', 'like', marker + '%')]):
            try:
                top = max(top, int((rec.doc_number or '').split('M')[1].split('/')[0]))
            except (IndexError, ValueError):
                continue
        return top + 1

    @api.onchange('amount', 'vat', 'tax', 'insure', 'lost', 'broken', 'transport')
    def _onchange_manual_amounts(self):
        """กรอกยอดแยกประเภทแล้วรวมหนี้ให้เอง เฉพาะรายการที่สร้างเอง"""
        for rec in self:
            if rec.is_manual:
                rec.total_debt = sum((rec[name] or 0.0) for name in self.COURT_FIELDS)

    @api.onchange('date_start')
    def _onchange_manual_debt_duration(self):
        """กรอกวันที่เริ่มหนี้แล้วนับจำนวนวันที่เป็นหนี้ให้เอง เฉพาะรายการที่สร้างเอง

        นับแบบเดียวกับรายการที่ดึงมา คือจากวันที่เริ่มหนี้ถึงวันนี้
        """
        for rec in self:
            if rec.is_manual:
                rec.debt_duration = ((date.today() - rec.date_start).days
                                     if rec.date_start else 0)

    @api.model
    def _refresh_manual_durations(self):
        """นับจำนวนวันที่เป็นหนี้ใหม่ให้รายการที่สร้างเอง ตอนกดดึงข้อมูล

        รายการที่ดึงมาได้ค่าใหม่ทุกครั้งที่ดึงอยู่แล้ว ของที่สร้างเองจึงต้องตามให้ทัน
        ไม่งั้นจะค้างอยู่ที่จำนวนวัน ณ วันที่กรอก
        """
        today = date.today()
        updated = 0
        for rec in self.sudo().search([('is_manual', '=', True),
                                       ('date_start', '!=', False)]):
            days = (today - rec.date_start).days
            if rec.debt_duration != days:
                rec.with_context(tracking_disable=True).write({'debt_duration': days})
                updated += 1
        return updated

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
        vals = {'court_adjust_date': False, 'court_adjust_uid': False}
        for _src, name, _label in DEBT_TYPES:
            vals['court_%s' % name] = 0.0
            vals['court_%s_set' % name] = False
        self.write(vals)
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
        """ดึงลูกหนี้ของบริษัทนี้จากฐาน MySQL แล้วแทนที่ข้อมูลเดิม

        ยึดชุดลูกหนี้เดียวกับเมนู "สรุปลูกหนี้ทั้งหมด" คือรายที่ค้างชำระสุทธิ > 0
        แล้วแบ่งบิลของลูกหนี้แต่ละรายเข้าบริษัทตามคำนำหน้าเลขใบกำกับเช่า
        ยอดแต่ละประเภทที่เก็บไว้จึงเป็น "ค้างสุทธิของบริษัทนี้" (ตั้งหนี้ - รับชำระ)

        ยอดที่ปรับตามคำสั่งศาลและสถานะชำระแล้ว ถูกเก็บไว้แล้วนำกลับมาใส่หลังดึง
        โดยจับคู่ด้วย (รหัสลูกค้า, สาขา)
        """
        prefix = self._company_prefix()
        _logger.info('baankheaw.debt_payment: เริ่มดึงข้อมูลของบริษัท %s (%s)',
                     prefix, BILL_PREFIX_COMPANY.get(prefix, '-'))

        # เก็บของเดิมที่ต้องรักษาไว้
        keep = {}
        for rec in self.sudo().search([('is_manual', '=', False)]):
            saved = {
                'payment_state': rec.payment_state,
                'court_adjust_date': rec.court_adjust_date,
                'court_adjust_uid': rec.court_adjust_uid.id,
                'court_note': rec.court_note,
            }
            for _src, name, _label in DEBT_TYPES:
                saved['court_%s' % name] = rec['court_%s' % name]
                saved['court_%s_set' % name] = rec['court_%s_set' % name]
            keep[(rec.cus_id or '', rec.branch_name or '')] = saved

        try:
            connection = pymysql.connect(**DB_CONFIG)
        except Exception as error:
            raise UserError('เชื่อมต่อฐานข้อมูลภายนอกไม่สำเร็จ: %s' % error)

        try:
            with connection.cursor() as cursor:
                cursor.execute(HEAD_QUERY)
                heads = {}
                for row in cursor.fetchall():
                    heads[((row.get('customer_id') or '').strip(),
                           (row.get('branch_id') or '').strip())] = row

                cursor.execute(BILL_QUERY)
                all_bills = cursor.fetchall()
                mine = {}
                for row in all_bills:
                    key = ((row.get('cus_key') or '').strip(),
                           (row.get('branch_key') or '').strip())
                    if key in heads and self._belongs_here(row['docid'], prefix):
                        mine.setdefault(key, []).append(row)

                product_map = self._fetch_products(
                    cursor, {r['docid'] for rows in mine.values() for r in rows})
        finally:
            connection.close()

        _logger.info('baankheaw.debt_payment: ลูกหนี้ในรายงาน %s ราย / บิลทั้งหมด %s ใบ '
                     '-> เป็นของบริษัทนี้ %s ราย %s ใบ',
                     len(heads), len(all_bills), len(mine),
                     sum(len(v) for v in mine.values()))

        today = date.today()
        company_name = BILL_PREFIX_COMPANY.get(prefix, '')
        vals_list = []
        for key, bills in mine.items():
            head = heads[key]
            summary = {
                'cus_id': head.get('customer_id'),
                'cus_fullname': head.get('cus_fullname'),
                'cus_cpnname': head.get('cus_cpnname'),
                'cus_tel': head.get('cus_tel'),
                'cus_cpntel': head.get('cus_cpntel'),
                'cus_address': head.get('cus_address'),
                'cus_cpnadd': head.get('cus_cpnadd'),
                'branch_name': head.get('branch_name'),
                'bill_company_name': company_name,
                'responsible_party': head.get('responsible_party'),
                'bill_status': head.get('bill_status_display'),
                'date_start': head.get('arh_date'),
                'due_date': head.get('due_date'),
                'debt_duration': head.get('debt_duration') or 0,
                # ยอดรวมของลูกหนี้รายนี้ทุกบริษัท ไว้ดูเทียบ
                'customer_gross_debt': float(head.get('total_debt') or 0.0),
                'customer_total_paid': float(head.get('total_paid') or 0.0),
                'customer_remaining': float(head.get('remaining_balance') or 0.0),
                'total_debt': 0.0,
                'bill_count': 0,
            }
            for _src, name, _label in DEBT_TYPES:
                summary[name] = 0.0

            bill_vals = []
            numbers = []
            for bill in bills:
                docid = bill['docid']
                numbers.append(docid)
                values = {}
                for src_key, name, _label in DEBT_TYPES:
                    values[name] = float(bill.get(src_key) or 0.0)
                    summary[name] += values[name]
                bill_total = float(bill.get('n_total') or 0.0)
                summary['total_debt'] += bill_total
                summary['bill_count'] += 1

                detail_text = ' / '.join(
                    '%s %s' % (label, _fmt(values[name]))
                    for _src, name, label in DEBT_TYPES
                    if abs(values[name]) > 0.005
                )

                product_vals = []
                product_texts = []
                for product in product_map.get(docid, []):
                    qty = float(product['qty'] or 0.0)
                    qty_return = float(product['qty_return'] or 0.0)
                    product_vals.append((0, 0, {
                        'doc_id': docid,
                        'cus_fullname': head.get('cus_fullname'),
                        'branch_name': head.get('branch_name'),
                        'product_code': product['product_code'],
                        'product_name': product['product_name'],
                        'qty': qty,
                        'qty_return': qty_return,
                        'qty_outstanding': qty - qty_return,
                    }))
                    product_texts.append('%s (จำนวน: %s)' % (
                        product['product_name'] or product['product_code'] or '-',
                        _fmt(qty)))

                bill_line = {
                    'cus_id': head.get('customer_id'),
                    'cus_fullname': head.get('cus_fullname'),
                    'branch_name': head.get('branch_name'),
                    'doc_id': docid,
                    'doc_date': bill.get('doc_date'),
                    'due_date': bill.get('due_date'),
                    'bill_status': bill.get('bill_status'),
                    'total_debt': bill_total,
                    'detail_text': detail_text,
                    'product_summary': ', '.join(product_texts),
                    'product_ids': product_vals,
                }
                bill_line.update(values)
                bill_vals.append((0, 0, bill_line))

            start = summary.get('date_start')
            if start:
                summary['debt_duration'] = summary['debt_duration'] or (today - start).days
            summary['bill_ids'] = bill_vals
            summary['bill_numbers'] = ', '.join(numbers)
            summary['is_manual'] = False
            vals_list.append(summary)

        # ลบเฉพาะรายการที่ดึงมา รายการที่สร้างเองต้องอยู่ต่อ
        self.sudo().search([('is_manual', '=', False)]).unlink()

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
        refreshed = self._refresh_manual_durations()
        _logger.info('baankheaw.debt_payment: สร้าง %s ราย (คืนค่าเดิม %s ราย '
                     'นับวันของรายการที่สร้างเองใหม่ %s ราย)',
                     len(vals_list), restored, refreshed)
        return True

    @api.model
    def _assign_doc_numbers(self):
        records = self.sudo().search([('is_manual', '=', False)])
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
    insure = fields.Float(string='ค่าประกัน', digits=(16, 2))
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
