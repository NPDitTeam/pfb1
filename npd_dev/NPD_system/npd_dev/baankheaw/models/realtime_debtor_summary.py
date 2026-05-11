# models/debtor_summary.py
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql


# from xlwt.ExcelMagic import ptgSheet # (ตามของเดิม) - Removed as it seems unused

class DebtorSummary(models.Model):
    _name = 'baankheaw.debtor_summary'
    _description = 'สรุปลูกหนี้ทั้งหมด'

    customer_id = fields.Char(string='ID รายการ')

    cus_fullname = fields.Char(string='ชื่อลูกค้า')
    cus_tel = fields.Char(string='เบอร์ลูกค้า')
    cus_address = fields.Char(string='ที่อยู่ลูกค้า')
    cus_cpntel = fields.Char(string='เบอร์บริษัท')
    cus_cpnadd = fields.Char(string='ที่อยู่บริษัท')

    # Keeping existing fields
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

    def action_update_realtime_data(self):
        self.env['baankheaw.debtor_summary'].sudo().fetch_and_store_realtime_data()

    @api.model
    def fetch_and_store_realtime_data(self):
        try:
            conn = pymysql.connect(
                host='150.95.26.61',
                user='greenhome',
                password='NPD@db789',
                database='npd_db',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )

            # Updated SQL Query with 'สถานะบิล'
            query = """
            SELECT
                d.customer_id,
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
                    SUM(COALESCE(h.arh_transport, 0)) AS ค่าขนส่ง,
                    SUM(COALESCE(h.arh_amount,0) + COALESCE(h.arh_vat,0) +
                        COALESCE(h.arh_tax,0) + COALESCE(h.arh_insure,0) +
                        COALESCE(h.arh_lost,0) + COALESCE(h.arh_transport,0) +
                        COALESCE(h.arh_broken,0)) AS หนี้รวม,
                    MIN(h.arh_date) AS วันที่เริ่มหนี้,
                    MAX(COALESCE(r.renth_date_return, r.renth_dateend)) AS วันที่ครบกำหนดชำระ,
                    CASE
                        WHEN COUNT(CASE WHEN r.renth_return = 'N' THEN 1 END) > 0 THEN 'N'
                        WHEN COUNT(CASE WHEN r.renth_return = 'Y' THEN 1 END) > 0 THEN 'Y'
                        ELSE NULL
                    END AS bill_status
                FROM npd_db.ar_head h
                JOIN npd_db.master_customer c ON TRIM(h.arh_cusid) = TRIM(c.cus_id)
                JOIN npd_db.master_branch b ON TRIM(h.branchid) = TRIM(b.branch_id)
                LEFT JOIN npd_db.rentorder_head r ON TRIM(h.arh_docid) = TRIM(r.renth_id)
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
            ORDER BY d.สาขา, d.ลูกค้า;
            """
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            # ล้างของเก่าด้วยสิทธิ์สูงสุด
            self.search([]).sudo().unlink()

            for row in results:
                self.create({
                    'customer_id': row.get('customer_id'),
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
                    'broken': 0,
                    'transport': row.get('transport', 0),
                    'total_debt': row.get('total_debt', 0),
                    'total_paid': row.get('total_paid', 0),
                    'remaining_balance': row.get('remaining_balance', 0),
                    'bill_status': row.get('bill_status_display'),
                    'responsible_party': row.get('responsible_party'),
                    'arh_date': row.get('arh_date'),
                    'due_date': row.get('due_date'),
                    'debt_duration': row.get('debt_duration', 0),
                })
        except Exception as e:
            raise UserError(f"❌ ดึงข้อมูลไม่สำเร็จ: {str(e)}")