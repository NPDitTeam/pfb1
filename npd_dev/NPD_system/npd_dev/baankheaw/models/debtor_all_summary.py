# -*- coding: utf-8 -*-
# models/debtor_all_summary.py
# สรุปลูกหนี้บ้านเขียวทั้งหมด (แสดงเลขบิล + รายการสินค้าในบิล)
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date
import logging
import pymysql

_logger = logging.getLogger(__name__)

# --- ตั้งค่าเชื่อมต่อฐานข้อมูลภายนอก (เหมือนรายงานตัวอื่นในโมดูลนี้) ---
DB_CONFIG = {
    'host': '150.95.26.61',
    'user': 'greenhome',
    'password': 'NPD@db789',
    'database': 'npd_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}

# ประเภทหนี้ 6 ช่อง (ลำดับตามคิวรีต้นฉบับ)
DEBT_TYPES = [
    ('b1', 'amount', 'ค่าเช่า'),
    ('b2', 'vat', 'Vat'),
    ('b3', 'tax', 'Tax'),
    ('b4', 'lost', 'ค่าปรับหาย'),
    ('b5', 'broken', 'ค่าปรับชำรุด'),
    ('b6', 'transport', 'ค่าขนส่ง'),
]

# ===== คิวรีระดับ "รายบิล" =====
# ตัดมาจากคิวรีต้นฉบับ แต่หยุดที่ชั้น 4 (ต่อ 1 บิล) แล้วไปรวมยอดต่อลูกค้าใน Python
# เหตุผล: GROUP_CONCAT ของ MySQL ตัดข้อความที่ 1024 ตัวอักษร ทำให้เลขบิลหายไป
# (ดูตัวอย่างข้อมูลเดิมที่ลงท้ายด้วย 'NB' แล้วขาด) การรวมใน Python จึงได้ครบทุกบิล
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

# ===== ค่าประกันคงเหลือ + ยอดรับชำระรวม (ต่อ ลูกค้า+สาขา) =====
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

# ===== รายการสินค้าในบิล (ดึงเฉพาะบิลที่ยังค้าง) =====
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


def _fmt(value):
    """จัดรูปแบบตัวเลขให้อ่านง่าย เช่น 1,117.06"""
    return '{:,.2f}'.format(value or 0.0)


class DebtorAllSummary(models.Model):
    _name = 'baankheaw.debtor_all_summary'
    _description = 'สรุปลูกหนี้บ้านเขียวทั้งหมด'
    _order = 'branch_name, cus_fullname'
    _rec_name = 'cus_fullname'

    # ข้อมูลลูกค้า
    cus_id = fields.Char(string='รหัสลูกค้า', index=True)
    cus_fullname = fields.Char(string='ลูกค้า')
    cus_cpnname = fields.Char(string='บริษัท')
    cus_tel = fields.Char(string='เบอร์ติดต่อ')
    cus_address = fields.Char(string='ที่อยู่ลูกค้า')
    cus_cpnadd = fields.Char(string='ที่อยู่บริษัท')
    cus_cpntel = fields.Char(string='เบอร์บริษัท')
    branch_name = fields.Char(string='สาขา', index=True)

    # ยอดหนี้แยกประเภท
    amount = fields.Float(string='ค่าเช่า', digits=(16, 2))
    vat = fields.Float(string='Vat', digits=(16, 2))
    tax = fields.Float(string='Tax', digits=(16, 2))
    lost = fields.Float(string='ค่าปรับหาย', digits=(16, 2))
    broken = fields.Float(string='ค่าปรับชำรุด', digits=(16, 2))
    transport = fields.Float(string='ค่าขนส่ง', digits=(16, 2))
    total_debt = fields.Float(string='หนี้รวม', digits=(16, 2))

    insure_balance = fields.Float(string='ค่าประกันคงเหลือ', digits=(16, 2))
    total_paid = fields.Float(string='รับชำระ', digits=(16, 2))

    # บิล
    bill_count = fields.Integer(string='จำนวนบิลค้าง')
    bill_numbers = fields.Text(string='เลขใบกำกับเช่า')
    bill_ids = fields.One2many('baankheaw.debtor_all_summary_bill', 'summary_id',
                               string='รายละเอียดบิลค้าง')

    date_start = fields.Date(string='วันที่เริ่มหนี้')
    due_date = fields.Date(string='วันที่ครบกำหนดชำระ')
    debt_duration = fields.Integer(string='ระยะเวลาที่เป็นหนี้ (วัน)')
    bill_status = fields.Char(string='สถานะบิล')

    @api.model
    def load_once_on_install(self):
        """ดึงข้อมูลครั้งเดียวตอนติดตั้งโมดูล

        - ถ้ามีข้อมูลอยู่แล้ว ข้ามไป (กันดึงซ้ำ)
        - ถ้าต่อฐานข้อมูลภายนอกไม่ได้ ให้บันทึก log ไว้เฉย ๆ ไม่ให้การติดตั้งล้มทั้งโมดูล
          (ดึงใหม่ได้จากเมนู Action → 📥 ดึงข้อมูลลูกหนี้บ้านเขียว)
        """
        if self.sudo().search_count([]):
            _logger.info('baankheaw.debtor_all_summary: มีข้อมูลอยู่แล้ว ข้ามการดึงตอนติดตั้ง')
            return True
        try:
            with self.env.cr.savepoint():
                return self.sudo().fetch_and_store_debtor_all_data()
        except Exception:
            _logger.exception('baankheaw.debtor_all_summary: ดึงข้อมูลตอนติดตั้งไม่สำเร็จ '
                              'ให้ดึงใหม่จากเมนู Action')
            return False

    def action_fetch_debtor_all_data(self):
        """ดึงข้อมูลด้วยตนเอง (ใช้กรณีตอนติดตั้งดึงไม่สำเร็จ) — ข้อมูลเดิมจะถูกแทนที่ทั้งหมด"""
        self.env['baankheaw.debtor_all_summary'].sudo().fetch_and_store_debtor_all_data()
        return True

    @api.model
    def _fetch_products(self, cursor, docids):
        """ดึงรายการสินค้าของบิลที่ยังค้าง แบ่งเป็นก้อนละ 500 กัน IN list ยาวเกิน"""
        products = {}
        docids = [d for d in docids if d]
        chunk_size = 500
        for i in range(0, len(docids), chunk_size):
            chunk = docids[i:i + chunk_size]
            placeholders = ','.join(['%s'] * len(chunk))
            cursor.execute(PRODUCT_QUERY.format(placeholders=placeholders), chunk)
            for row in cursor.fetchall():
                products.setdefault(row['docid'], []).append(row)
        return products

    @api.model
    def fetch_and_store_debtor_all_data(self):
        """ดึงข้อมูลลูกหนี้ทั้งหมด (ระดับบิล) แล้วรวมยอดต่อ ลูกค้า+สาขา"""
        conn = None
        try:
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()

            cursor.execute(BILL_QUERY)
            bill_rows = cursor.fetchall()

            cursor.execute(INSURE_QUERY)
            insure_map = {
                (r['cus_key'], r['branch_key']): r
                for r in cursor.fetchall()
            }

            docids = sorted({r['docid'] for r in bill_rows})
            product_map = self._fetch_products(cursor, docids)
        except Exception as e:
            _logger.exception('baankheaw.debtor_all_summary: fetch failed')
            raise UserError(f"❌ ดึงข้อมูลลูกหนี้บ้านเขียวไม่สำเร็จ: {str(e)}")
        finally:
            if conn:
                conn.close()

        # ===== รวมยอดต่อ ลูกค้า + สาขา =====
        summaries = {}
        for row in bill_rows:
            key = (row['cus_key'], row['branch_key'])
            summary = summaries.get(key)
            if not summary:
                summary = summaries[key] = {
                    'cus_id': row['cus_key'],
                    'cus_fullname': row['cus_fullname'],
                    'cus_cpnname': row['cus_cpnname'],
                    # คิวรีต้นฉบับใช้ cus_cpntel เป็น "เบอร์ติดต่อ" ด้วย
                    'cus_tel': row['cus_cpntel'],
                    'cus_cpntel': row['cus_cpntel'],
                    'cus_address': row['cus_address'],
                    'cus_cpnadd': row['cus_cpnadd'],
                    'branch_name': row['branch_name'],
                    'amount': 0.0, 'vat': 0.0, 'tax': 0.0,
                    'lost': 0.0, 'broken': 0.0, 'transport': 0.0,
                    'total_debt': 0.0,
                    'bill_count': 0,
                    'date_start': None,
                    'due_date': None,
                    'bill_status': 'ไม่มีข้อมูล',
                    'bill_texts': [],
                    'bill_ids': [],
                }

            values = {name: float(row[col] or 0.0) for col, name, _label in DEBT_TYPES}
            bill_total = float(row['b_total'] or 0.0)

            for name in values:
                summary[name] += values[name]
            summary['total_debt'] += bill_total
            summary['bill_count'] += 1

            doc_date = row['doc_date']
            if doc_date and (not summary['date_start'] or doc_date < summary['date_start']):
                summary['date_start'] = doc_date
            bill_due = row['due_date']
            if bill_due and (not summary['due_date'] or bill_due > summary['due_date']):
                summary['due_date'] = bill_due
            # ถ้ามีบิลใดยังไม่ปิด ให้ถือว่าลูกค้ารายนี้ "ยังไม่ปิดบิล"
            if row['bill_status'] == 'ยังไม่ปิดบิล':
                summary['bill_status'] = 'ยังไม่ปิดบิล'
            elif row['bill_status'] == 'ปิดบิล' and summary['bill_status'] != 'ยังไม่ปิดบิล':
                summary['bill_status'] = 'ปิดบิล'

            # ข้อความสรุปประเภทหนี้ของบิลนี้ เช่น "ค่าเช่า : 1,117.06 ; Vat : 78.19"
            detail_text = ' ; '.join(
                '%s : %s' % (label, _fmt(values[name]))
                for _col, name, label in DEBT_TYPES
                if values[name] > 0.01
            )
            summary['bill_texts'].append('%s : %s' % (row['docid'], detail_text))

            # ===== รายการสินค้าในบิล =====
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
                    product['product_name'] or product['product_code'] or '-',
                    _fmt(qty),
                ))

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
            if summary['total_debt'] <= 0.01:
                continue
            insure = insure_map.get(key) or {}
            summary['insure_balance'] = round(float(insure.get('insure_balance') or 0.0), 2)
            summary['total_paid'] = round(float(insure.get('total_paid') or 0.0), 2)
            for _col, name, _label in DEBT_TYPES:
                summary[name] = round(summary[name], 2)
            summary['total_debt'] = round(summary['total_debt'], 2)
            summary['bill_numbers'] = '\n'.join(summary.pop('bill_texts'))
            summary['debt_duration'] = (today - summary['date_start']).days \
                if summary['date_start'] else 0
            vals_list.append(summary)

        # ล้างของเก่า (บิล/สินค้าถูกลบตาม ondelete='cascade')
        self.sudo().search([]).unlink()

        # สร้างทีละก้อน กันข้อมูลชุดใหญ่กินหน่วยความจำ
        batch_size = 100
        for i in range(0, len(vals_list), batch_size):
            self.sudo().create(vals_list[i:i + batch_size])

        _logger.info('baankheaw.debtor_all_summary: created %s customers / %s bills',
                     len(vals_list), len(bill_rows))
        return True


class DebtorAllSummaryBill(models.Model):
    _name = 'baankheaw.debtor_all_summary_bill'
    _description = 'บิลค้างชำระของลูกหนี้บ้านเขียว'
    _order = 'doc_id'
    _rec_name = 'doc_id'

    summary_id = fields.Many2one('baankheaw.debtor_all_summary', string='ลูกหนี้',
                                 required=True, ondelete='cascade', index=True)
    # เก็บเป็นคอลัมน์ตรง ๆ (ไม่ใช้ related store) เพื่อเลี่ยง recompute ตอนสร้างข้อมูลชุดใหญ่
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
    product_ids = fields.One2many('baankheaw.debtor_all_summary_product', 'bill_id',
                                  string='รายการสินค้าในบิล')


class DebtorAllSummaryProduct(models.Model):
    _name = 'baankheaw.debtor_all_summary_product'
    _description = 'รายการสินค้าในบิลลูกหนี้บ้านเขียว'
    _order = 'product_code'
    _rec_name = 'product_name'

    bill_id = fields.Many2one('baankheaw.debtor_all_summary_bill', string='บิล',
                              required=True, ondelete='cascade', index=True)
    doc_id = fields.Char(string='เลขใบกำกับเช่า')
    cus_fullname = fields.Char(string='ลูกค้า')
    branch_name = fields.Char(string='สาขา')

    product_code = fields.Char(string='รหัสสินค้า')
    product_name = fields.Char(string='ชื่อสินค้า')
    qty = fields.Float(string='จำนวนที่เช่า', digits=(16, 2))
    qty_return = fields.Float(string='จำนวนที่คืน', digits=(16, 2))
    qty_outstanding = fields.Float(string='คงค้าง', digits=(16, 2))
