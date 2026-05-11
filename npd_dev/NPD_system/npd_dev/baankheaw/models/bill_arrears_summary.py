# models/bill_arrears_summary.py
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql


class BillArrearsSummary(models.Model):
    _name = 'baankheaw.bill_arrears_summary'
    _description = 'สรุปยอดบิลค้างชำระทั้งหมด'
    _order = 'customer_id, doc_id'

    # Fields corresponding to the SQL Query results
    doc_id = fields.Char(string='เลขที่เอกสาร')
    customer_id = fields.Char(string='รหัสลูกค้า')
    cus_fullname = fields.Char(string='ลูกค้า')
    cus_cpnname = fields.Char(string='บริษัท')
    branch_name = fields.Char(string='สาขา')
    date_start = fields.Date(string='วันเช่าเริ่มต้น')
    date_end = fields.Date(string='วันเช่าสิ้นสุด')
    bill_status = fields.Char(string='สถานะบิล')

    # Financial details
    amount = fields.Float(string='ค่าเช่า')
    vat = fields.Float(string='Vat')
    tax = fields.Float(string='Tax')
    insure = fields.Float(string='ค่าประกัน')
    lost = fields.Float(string='ค่าปรับหาย')
    broken = fields.Float(string='ค่าเสียหาย')
    transport = fields.Float(string='ค่าขนส่ง')

    total_bill_debt = fields.Float(string='ยอดหนี้ทั้งหมด')
    total_paid = fields.Float(string='รับชำระ')
    remaining_balance = fields.Float(string='คงเหลือ')

    # Odoo Standard Field for monetary widget in XML
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        readonly=True
    )

    # ไม่มี constraint - อนุญาตให้ซ้ำได้

    def action_update_realtime_data_bill(self):
        """Action button to trigger data fetching."""
        self.env['baankheaw.bill_arrears_summary'].sudo().fetch_and_store_realtime_data_bill()

    @api.model
    def fetch_and_store_realtime_data_bill(self):
        """Connects to external DB, executes query, and updates Odoo records."""
        try:
            # Database connection details
            conn = pymysql.connect(
                host='150.95.26.61',
                user='greenhome',
                password='NPD@db789',
                database='npd_db',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )

            # SQL Query (Original format without GROUP BY)
            query = """
            SELECT
              h.arh_docid                       AS เลขที่เอกสาร,
              h.arh_cusid                       AS รหัสลูกค้า,
              c.cus_fullname                    AS ลูกค้า,
              c.cus_cpnname                     AS บริษัท,
              b.branch_name                     AS สาขา,
              rh.renth_datestart                AS วันเช่าเริ่มต้น,
              rh.renth_dateend                  AS วันเช่าสิ้นสุด,
              CASE 
                WHEN rh.renth_return = 'Y' THEN 'ปิดบิล'
                WHEN rh.renth_return = 'N' THEN 'ยังไม่ปิดบิล'
                ELSE NULL
              END                               AS สถานะบิล,
              h.arh_amount                      AS ค่าเช่า,
              h.arh_vat                         AS Vat,
              h.arh_tax                         AS tax,
              h.arh_insure                      AS ค่าประกัน,
              h.arh_lost                        AS ค่าปรับหาย,
              h.arh_broken                      AS ค่าเสียหาย,
              h.arh_transport                   AS ค่าขนส่ง,
              (
                COALESCE(h.arh_amount,0) +
                COALESCE(h.arh_vat,0) +
                COALESCE(h.arh_tax,0) +
                COALESCE(h.arh_insure,0) +
                COALESCE(h.arh_lost,0) +
                COALESCE(h.arh_broken,0) +
                COALESCE(h.arh_transport,0)
              )                                 AS ยอดหนี้ทั้งหมด,
              COALESCE(repay_sum.total_repay, 0) AS รับชำระ,
              (
                COALESCE(h.arh_amount,0) +
                COALESCE(h.arh_vat,0) +
                COALESCE(h.arh_tax,0) +
                COALESCE(h.arh_insure,0) +
                COALESCE(h.arh_lost,0) +
                COALESCE(h.arh_broken,0) +
                COALESCE(h.arh_transport,0)
              ) - COALESCE(repay_sum.total_repay, 0) AS คงเหลือ
            FROM npd_db.ar_head h
            JOIN npd_db.master_customer c
              ON TRIM(h.arh_cusid) = TRIM(c.cus_id)
            JOIN npd_db.master_branch b
              ON TRIM(h.branchid) = TRIM(b.branch_id)
            LEFT JOIN npd_db.rentorder_head rh
              ON rh.renth_id = h.arh_docid
              AND rh.renth_cancel = 'N'
            LEFT JOIN (
              SELECT 
                arh_num,
                SUM(
                  COALESCE(arp_amount,0) +
                  COALESCE(arp_vat,0) +
                  COALESCE(arp_tax,0) +
                  COALESCE(arp_insure,0) +
                  COALESCE(arp_lost,0) +
                  COALESCE(arp_broken,0) +
                  COALESCE(arp_transport,0)
                ) AS total_repay
              FROM npd_db.ar_repay
              WHERE cancel = 'N'
              GROUP BY arh_num
            ) repay_sum
              ON repay_sum.arh_num = h.num
            WHERE h.cancel = 'N'
              AND (
                COALESCE(h.arh_amount,0) +
                COALESCE(h.arh_vat,0) +
                COALESCE(h.arh_tax,0) +
                COALESCE(h.arh_insure,0) +
                COALESCE(h.arh_lost,0) +
                COALESCE(h.arh_broken,0) +
                COALESCE(h.arh_transport,0)
              ) - COALESCE(repay_sum.total_repay, 0) > 0
            ORDER BY c.cus_fullname, h.arh_docid;
            """

            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            # Clear old records with sudo
            self.search([]).sudo().unlink()

            # Create new records
            for row in results:
                # ข้ามถ้าไม่มีเลขที่เอกสารหรือรหัสลูกค้า
                if not row.get('เลขที่เอกสาร') or not row.get('รหัสลูกค้า'):
                    continue

                self.create({
                    'doc_id': row.get('เลขที่เอกสาร'),
                    'customer_id': row.get('รหัสลูกค้า'),
                    'cus_fullname': row.get('ลูกค้า'),
                    'cus_cpnname': row.get('บริษัท'),
                    'branch_name': row.get('สาขา'),
                    'date_start': row.get('วันเช่าเริ่มต้น'),
                    'date_end': row.get('วันเช่าสิ้นสุด'),
                    'bill_status': row.get('สถานะบิล'),
                    'amount': row.get('ค่าเช่า', 0.0),
                    'vat': row.get('Vat', 0.0),
                    'tax': row.get('tax', 0.0),
                    'insure': row.get('ค่าประกัน', 0.0),
                    'lost': row.get('ค่าปรับหาย', 0.0),
                    'broken': row.get('ค่าเสียหาย', 0.0),
                    'transport': row.get('ค่าขนส่ง', 0.0),
                    'total_bill_debt': row.get('ยอดหนี้ทั้งหมด', 0.0),
                    'total_paid': row.get('รับชำระ', 0.0),
                    'remaining_balance': row.get('คงเหลือ', 0.0),
                })

        except Exception as e:
            error_msg = f"❌ ดึงข้อมูลไม่สำเร็จ: {str(e)}"
            raise UserError(error_msg)