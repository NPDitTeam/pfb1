# -*- coding: utf-8 -*-
"""สรุปลูกหนี้ทั้งหมด — หัวลูกหนี้ + บิลค้างชำระ + รายการสินค้าในบิล

หัวลูกหนี้ยังใช้คิวรีเดิม (จัดกลุ่มตามลูกค้า+สาขา หักรับชำระทั้งก้อน)
ส่วนบิลกับรายการสินค้าเป็นของใหม่ คิดยอดคงค้างแยกทีละบิลทีละประเภท
โดยใช้ตารางและเงื่อนไขชุดเดียวกัน ผลรวมของบิลจึงเท่ากับ "ค้างชำระสุทธิ" ของหัวเสมอ
"""
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
import pymysql

_logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': '150.95.26.61',
    'user': 'greenhome',
    'password': 'NPD@db789',
    'database': 'npd_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}

# ประเภทหนี้ 7 ช่อง เรียงตามที่แสดงบนหน้าจอ
DEBT_TYPES = [
    ('amount', 'ค่าเช่า'),
    ('vat', 'Vat'),
    ('tax', 'Tax'),
    ('insure', 'ค่าประกัน'),
    ('lost', 'ค่าปรับหาย'),
    ('broken', 'ค่าปรับชำรุด'),
    ('transport', 'ค่าขนส่ง'),
]

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

# ยอดคงค้างแยกทีละบิลทีละประเภท (ตั้งหนี้ - รับชำระ)
# ใช้ตารางและเงื่อนไขชุดเดียวกับคิวรีหัว ผลรวมบิลของลูกค้า+สาขาหนึ่ง ๆ
# จึงเท่ากับ remaining_balance ของหัวเสมอ
#
# ไม่ตัดยอดติดลบทิ้ง เพราะถ้าตัด ผลรวมของบิลจะไม่ตรงกับหัวอีกต่อไป
# (ลูกค้าที่จ่ายเกินในประเภทหนึ่ง แล้วไปขาดในอีกประเภท)
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


def _fmt(value):
    return '{:,.2f}'.format(value or 0.0)


class DebtorSummary(models.Model):
    _name = 'baankheaw.debtor_summary'
    _description = 'สรุปลูกหนี้ทั้งหมด'

    customer_id = fields.Char(string='ID รายการ', index=True)
    branch_id = fields.Char(string='รหัสสาขา', index=True)

    cus_fullname = fields.Char(string='ชื่อลูกค้า')
    cus_tel = fields.Char(string='เบอร์ลูกค้า')
    cus_address = fields.Char(string='ที่อยู่ลูกค้า')
    cus_cpntel = fields.Char(string='เบอร์บริษัท')
    cus_cpnadd = fields.Char(string='ที่อยู่บริษัท')

    bill_status = fields.Char(string='สถานะบิล')
    debt_duration = fields.Integer(string='ระยะเวลาที่เป็นหนี้ (วัน)')
    responsible_party = fields.Char(string='ผู้รับผิดชอบ')

    branch_name = fields.Char(string='สาขา')
    cus_cpnname = fields.Char(string='ชื่อบริษัท')
    amount = fields.Float(string='ค่าเช่า')
    vat = fields.Float(string='Vat')
    tax = fields.Float(string='Tax')
    insure = fields.Float(string='ค่าประกัน')
    lost = fields.Float(string='ค่าปรับหาย')
    broken = fields.Float(string='ค่าปรับชำรุด')
    transport = fields.Float(string='ค่าขนส่ง')

    total_debt = fields.Float(string='หนี้รวม')
    total_paid = fields.Float(string='ยอดรับชำระ')
    remaining_balance = fields.Float(string='ค้างชำระสุทธิ')
    arh_date = fields.Date(string='วันที่เริ่มหนี้')
    due_date = fields.Date(string='วันที่ครบกำหนดชำระ')

    # ===== รายละเอียดที่ดึงเพิ่ม =====
    bill_ids = fields.One2many('baankheaw.debtor_summary_bill', 'summary_id',
                               string='บิลค้างชำระ')
    product_ids = fields.One2many('baankheaw.debtor_summary_product', 'summary_id',
                                  string='รายการสินค้า')
    bill_count = fields.Integer(string='จำนวนบิล')
    bill_numbers = fields.Text(string='เลขใบกำกับเช่า')

    def action_update_realtime_data(self):
        self.env['baankheaw.debtor_summary'].sudo().fetch_and_store_realtime_data()

    @api.model
    def _fetch_products(self, cursor, docids):
        """ดึงรายการสินค้าของบิล แบ่งเป็นก้อนละ 500 กัน IN list ยาวเกิน"""
        products = {}
        docids = [d for d in docids if d]
        for i in range(0, len(docids), 500):
            chunk = docids[i:i + 500]
            placeholders = ', '.join(['%s'] * len(chunk))
            cursor.execute(PRODUCT_QUERY.format(placeholders=placeholders), chunk)
            for row in cursor.fetchall():
                products.setdefault(row['docid'], []).append(row)
        return products

    @api.model
    def fetch_and_store_realtime_data(self):
        try:
            conn = pymysql.connect(**DB_CONFIG)
        except Exception as error:
            raise UserError('❌ เชื่อมต่อฐานข้อมูลภายนอกไม่สำเร็จ: %s' % error)

        try:
            with conn.cursor() as cursor:
                cursor.execute(HEAD_QUERY)
                head_rows = cursor.fetchall()

                cursor.execute(BILL_QUERY)
                bill_rows = cursor.fetchall()

                # เก็บเฉพาะบิลของลูกหนี้ที่อยู่ในรายงาน (ค้างสุทธิ > 0)
                wanted = {
                    ((row.get('customer_id') or '').strip(),
                     (row.get('branch_id') or '').strip())
                    for row in head_rows
                }
                bills_by_key = {}
                for row in bill_rows:
                    key = ((row.get('cus_key') or '').strip(),
                           (row.get('branch_key') or '').strip())
                    if key in wanted:
                        bills_by_key.setdefault(key, []).append(row)

                product_map = self._fetch_products(
                    cursor,
                    {row['docid'] for rows in bills_by_key.values() for row in rows})
        finally:
            conn.close()

        vals_list = []
        for row in head_rows:
            key = ((row.get('customer_id') or '').strip(),
                   (row.get('branch_id') or '').strip())
            bill_vals = []
            product_vals = []
            numbers = []
            for bill in bills_by_key.get(key, []):
                docid = bill['docid']
                numbers.append(docid)
                detail = ' / '.join(
                    '%s %s' % (label, _fmt(bill['n_%s' % name]))
                    for name, label in DEBT_TYPES
                    if abs(bill['n_%s' % name] or 0.0) > 0.005
                )
                product_texts = []
                bill_products = []
                for product in product_map.get(docid, []):
                    qty = float(product['qty'] or 0.0)
                    qty_return = float(product['qty_return'] or 0.0)
                    line = {
                        'doc_id': docid,
                        'cus_fullname': row.get('cus_fullname'),
                        'branch_name': row.get('branch_name'),
                        'product_code': product['product_code'],
                        'product_name': product['product_name'],
                        'qty': qty,
                        'qty_return': qty_return,
                        'qty_outstanding': qty - qty_return,
                    }
                    bill_products.append((0, 0, line))
                    product_vals.append((0, 0, dict(line)))
                    product_texts.append('%s (จำนวน: %s)' % (
                        product['product_name'] or product['product_code'] or '-',
                        _fmt(qty)))

                bill_vals.append((0, 0, {
                    'cus_id': row.get('customer_id'),
                    'cus_fullname': row.get('cus_fullname'),
                    'branch_name': row.get('branch_name'),
                    'doc_id': docid,
                    'doc_date': bill.get('doc_date'),
                    'due_date': bill.get('due_date'),
                    'bill_status': bill.get('bill_status'),
                    'amount': bill['n_amount'],
                    'vat': bill['n_vat'],
                    'tax': bill['n_tax'],
                    'insure': bill['n_insure'],
                    'lost': bill['n_lost'],
                    'broken': bill['n_broken'],
                    'transport': bill['n_transport'],
                    'total_debt': bill['n_total'],
                    'detail_text': detail,
                    'product_summary': ', '.join(product_texts),
                    'product_ids': bill_products,
                }))

            vals_list.append({
                'customer_id': row.get('customer_id'),
                'branch_id': row.get('branch_id'),
                'cus_fullname': row.get('cus_fullname'),
                'cus_tel': row.get('cus_tel'),
                'cus_address': row.get('cus_address'),
                'cus_cpnname': row.get('cus_cpnname'),
                'cus_cpntel': row.get('cus_cpntel'),
                'cus_cpnadd': row.get('cus_cpnadd'),
                'branch_name': row.get('branch_name'),
                'amount': row.get('amount', 0),
                'vat': row.get('vat', 0),
                'tax': row.get('tax', 0),
                'insure': row.get('insure', 0),
                'lost': row.get('lost', 0),
                'broken': row.get('broken', 0),
                'transport': row.get('transport', 0),
                'total_debt': row.get('total_debt', 0),
                'total_paid': row.get('total_paid', 0),
                'remaining_balance': row.get('remaining_balance', 0),
                'bill_status': row.get('bill_status_display'),
                'responsible_party': row.get('responsible_party'),
                'arh_date': row.get('arh_date'),
                'due_date': row.get('due_date'),
                'debt_duration': row.get('debt_duration', 0),
                'bill_ids': bill_vals,
                'product_ids': product_vals,
                'bill_count': len(bill_vals),
                'bill_numbers': ', '.join(numbers),
            })

        self.sudo().search([]).unlink()
        for i in range(0, len(vals_list), 100):
            self.sudo().create(vals_list[i:i + 100])

        _logger.info('baankheaw.debtor_summary: ลูกหนี้ %s ราย บิล %s ใบ',
                     len(vals_list), sum(v['bill_count'] for v in vals_list))
        return True


class DebtorSummaryBill(models.Model):
    _name = 'baankheaw.debtor_summary_bill'
    _description = 'บิลค้างชำระของลูกหนี้'
    _order = 'doc_id'
    _rec_name = 'doc_id'

    summary_id = fields.Many2one('baankheaw.debtor_summary', string='ลูกหนี้',
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
    product_ids = fields.One2many('baankheaw.debtor_summary_product', 'bill_id',
                                  string='รายการสินค้าในบิล')


class DebtorSummaryProduct(models.Model):
    _name = 'baankheaw.debtor_summary_product'
    _description = 'รายการสินค้าในบิลลูกหนี้'
    _order = 'doc_id, product_code'
    _rec_name = 'product_name'

    bill_id = fields.Many2one('baankheaw.debtor_summary_bill', string='บิล',
                              ondelete='cascade', index=True)
    summary_id = fields.Many2one('baankheaw.debtor_summary', string='ลูกหนี้',
                                 ondelete='cascade', index=True)
    doc_id = fields.Char(string='เลขใบกำกับเช่า', index=True)
    cus_fullname = fields.Char(string='ลูกค้า')
    branch_name = fields.Char(string='สาขา')

    product_code = fields.Char(string='รหัสสินค้า')
    product_name = fields.Char(string='ชื่อสินค้า')
    qty = fields.Float(string='จำนวนที่เช่า', digits=(16, 2))
    qty_return = fields.Float(string='จำนวนที่คืน', digits=(16, 2))
    qty_outstanding = fields.Float(string='คงค้าง', digits=(16, 2))
