# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import pymysql
import logging

_logger = logging.getLogger(__name__)


class SalesCommissionReport(models.Model):
    _name = 'npd.sales.commission.report'
    _description = 'รายงานค่าคอมบ้านเขียว'
    _order = 'report_period desc, branch_id, report_type, salesperson_name'

    # คอลัมน์วันที่ (ปี/เดือน) - แสดงหน้าสุด
    report_period = fields.Char(string='ปี/เดือน')

    # Fields ตาม query ใหม่
    report_type = fields.Selection([
        ('branch', 'สาขา'),
        ('sales', 'เซลล์')
    ], string='ประเภท')
    branch_id = fields.Char(string='รหัสสาขา')
    branch_id_odoo = fields.Char(string='รหัสสาขา (Odoo)')
    branch_name = fields.Char(string='สาขา')
    employee_id = fields.Many2one('hr.employee', string='พนักงาน')
    employee_code = fields.Char(string='รหัสพนักงาน')
    salesperson_name = fields.Char(string='ชื่อเซลล์')

    # ค่าเช่า
    initial_rent = fields.Float(string='ค่าเช่าเริ่มต้น', digits=(16, 2))
    discount = fields.Float(string='ส่วนลด', digits=(16, 2))
    rent_difference = fields.Float(string='ส่วนต่างค่าเช่า', digits=(16, 2))
    total_rent_revenue = fields.Float(string='รายได้ค่าเช่ารวม', digits=(16, 2))

    # ค้างชำระ
    outstanding_bill_count = fields.Integer(string='จำนวนบิลค้างชำระ')
    total_outstanding = fields.Float(string='ค้างชำระรวม', digits=(16, 2))
    total_paid = fields.Float(string='รับชำระ', digits=(16, 2))
    net_outstanding = fields.Float(string='ค้างชำระสุทธิ', digits=(16, 2))

    # หนี้เก่า
    old_debt_paid = fields.Float(string='รับชำระบิลเก่า', digits=(16, 2))

    # ยอดสุทธิ
    net_total = fields.Float(string='ยอดสุทธิ', digits=(16, 2))

    # ช่วงวันที่รายงาน
    report_date_from = fields.Date(string='จากวันที่')
    report_date_to = fields.Date(string='ถึงวันที่')

    def action_refresh_data(self):
        """Refresh data from external database"""
        self.env['npd.sales.commission.report'].sudo().fetch_all_commission_data()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _get_employee_by_salesperson(self, salesperson_name):
        """
        ค้นหา employee จากชื่อเซลล์ และดึง x_user_id มาเป็นรหัสพนักงาน
        รูปแบบชื่อจาก query: "รหัส - ชื่อ นามสกุล" เช่น "0473 - ปรารถนา กล่อมแจ้ง"
        รูปแบบชื่อใน hr.employee: "คำนำหน้าชื่อ นามสกุล" เช่น "นางสาวปรารถนา กล่อมแจ้ง"
        """
        if not salesperson_name:
            return None, ''

        salesperson_name = salesperson_name.strip()
        employee = None
        employee_code = ''

        # แยกรหัสออกจากชื่อ (รูปแบบ: "รหัส - ชื่อ")
        code_from_name = ''
        name_part = salesperson_name
        if ' - ' in salesperson_name:
            parts = salesperson_name.split(' - ', 1)
            code_from_name = parts[0].strip()
            name_part = parts[1].strip() if len(parts) > 1 else ''

        # 1. ค้นหาจาก x_user_id ที่ตรงกับรหัสที่แยกได้
        if code_from_name:
            employee = self.env['hr.employee'].sudo().search([
                ('x_user_id', '=', code_from_name)
            ], limit=1)
            if employee:
                _logger.info(f"Found employee by x_user_id: {code_from_name} -> {employee.name}")
                return employee, code_from_name

        # 2. ค้นหาจากชื่อ (ถ้าไม่เจอจากรหัส)
        if name_part:
            # แยกชื่อ-นามสกุล
            name_parts = name_part.split()
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = name_parts[-1]

                # ค้นหา employee ที่มีทั้งชื่อและนามสกุล
                employee = self.env['hr.employee'].sudo().search([
                    '&',
                    ('name', 'ilike', first_name),
                    ('name', 'ilike', last_name)
                ], limit=1)

        # ดึง x_user_id จาก employee ที่เจอ
        if employee:
            if hasattr(employee, 'x_user_id') and employee.x_user_id:
                employee_code = str(employee.x_user_id)
            return employee, employee_code

        return None, ''

    def _get_branch_id_odoo(self, branch_name_value):
        """ค้นหารหัสสาขาใน Odoo จาก res.branch โดยจับคู่ชื่อสาขา"""
        branch_id_odoo = ''
        if branch_name_value:
            branch_odoo = None
            branch_name_clean = branch_name_value.strip()

            # 1. ค้นหาแบบ ilike (contains)
            branch_odoo = self.env['res.branch'].sudo().search([
                ('name', 'ilike', branch_name_clean)
            ], limit=1)

            # 2. ถ้าไม่เจอ ลองค้นหาจากคำแรกของชื่อสาขา
            if not branch_odoo:
                first_word = branch_name_clean.split()[0] if branch_name_clean.split() else ''
                if first_word:
                    branch_odoo = self.env['res.branch'].sudo().search([
                        ('name', 'ilike', first_word)
                    ], limit=1)

            # 3. ถ้าไม่เจอ ลองค้นหาจากคำสำคัญ
            if not branch_odoo:
                keywords = branch_name_clean.replace('สาขา', '').replace('จังหวัด', '').strip()
                if keywords:
                    branch_odoo = self.env['res.branch'].sudo().search([
                        ('name', 'ilike', keywords)
                    ], limit=1)

            if branch_odoo:
                branch_id_odoo = str(branch_odoo.id)

        return branch_id_odoo

    @api.model
    def fetch_all_commission_data(self):
        """
        ดึงข้อมูลทั้งหมดตั้งแต่ ม.ค. ถึงเดือนปัจจุบัน (ใช้ query ใหม่ที่แยกตามเดือนอัตโนมัติ)
        ใช้สำหรับ Scheduled Action (การกระทำที่กำหนดไว้)
        """
        _logger.info("Starting fetch_all_commission_data with new monthly query...")

        try:
            conn = pymysql.connect(
                host='150.95.26.61',
                user='greenhome',
                password='NPD@db789',
                database='npd_db',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )

            # Query ใหม่ที่ดึงข้อมูลแยกตามเดือนอัตโนมัติตั้งแต่ ม.ค. ถึงเดือนปัจจุบัน
            query = """
-- ===== สร้างตารางเดือน ตั้งแต่ ม.ค. ถึงเดือนปัจจุบัน =====
WITH months AS (
    SELECT 1 AS m UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
    UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8
    UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12
),
month_range AS (
    SELECT
        m,
        CONCAT(YEAR(CURDATE()), '/', LPAD(m, 2, '0')) AS period_label,
        DATE(CONCAT(YEAR(CURDATE()), '-', LPAD(m, 2, '0'), '-01')) AS month_start,
        LAST_DAY(DATE(CONCAT(YEAR(CURDATE()), '-', LPAD(m, 2, '0'), '-01'))) AS month_end
    FROM months
    WHERE m <= MONTH(CURDATE())
),
year_range AS (
    SELECT
        DATE(CONCAT(YEAR(CURDATE()), '-01-01')) AS year_start,
        CURDATE() AS today
)

-- ===== ยอดสาขา (ไม่มีเซลล์) แยกตามเดือน =====
SELECT
    mr.period_label AS report_period,
    'สาขา' AS report_type,
    mb.branch_id AS branch_id,
    mb.branch_name AS branch_name,
    NULL AS salesperson_name,
    COALESCE(rent.initial_rent, 0) AS initial_rent,
    COALESCE(rent.discount, 0) AS discount,
    COALESCE(rent.rent_difference, 0) AS rent_difference,
    COALESCE(rent.initial_rent, 0) - COALESCE(rent.discount, 0) + COALESCE(rent.rent_difference, 0) AS total_rent_revenue,
    COALESCE(ar.outstanding_bill_count, 0) AS outstanding_bill_count,
    COALESCE(ar.total_outstanding, 0) AS total_outstanding,
    COALESCE(ar.total_paid, 0) AS total_paid,
    COALESCE(ar.total_outstanding, 0) - COALESCE(ar.total_paid, 0) AS net_outstanding,
    COALESCE(ar_old.old_debt_paid, 0) AS old_debt_paid,
    (COALESCE(rent.initial_rent, 0) - COALESCE(rent.discount, 0) + COALESCE(rent.rent_difference, 0))
    - (COALESCE(ar.total_outstanding, 0) - COALESCE(ar.total_paid, 0))
    + COALESCE(ar_old.old_debt_paid, 0) AS net_total,
    mr.month_start AS report_date_from,
    mr.month_end AS report_date_to

FROM month_range mr
CROSS JOIN npd_db.master_branch mb
CROSS JOIN year_range yr

-- ส่วนค่าเช่า (เฉพาะบิลที่ไม่มีเซลล์) แยกตามเดือน
LEFT JOIN (
    SELECT
        branchid,
        report_month,
        SUM(initial_rent) AS initial_rent,
        SUM(discount) AS discount,
        SUM(rent_difference) AS rent_difference
    FROM (
        SELECT
            branchid,
            MONTH(renth_datestart) AS report_month,
            ROUND(renth_rentbegin / 1.07, 2) AS initial_rent,
            0 AS discount,
            0 AS rent_difference
        FROM npd_db.rentorder_head
        WHERE YEAR(renth_datestart) = YEAR(CURDATE())
          AND DATE(renth_datestart) <= CURDATE()
          AND renth_cancel = 'N'
          AND renth_bookingcancel = 'N'
          AND (renth_salename IS NULL OR TRIM(renth_salename) = '')

        UNION ALL

        SELECT
            branchid,
            MONTH(renth_date_return) AS report_month,
            0 AS initial_rent,
            ROUND(renth_discount_return / 1.07, 2) AS discount,
            ROUND(
                CASE
                    WHEN DATEDIFF(renth_dateend, renth_datestart) > 0
                    THEN (renth_rentbegin / DATEDIFF(renth_dateend, renth_datestart))
                         * DATEDIFF(renth_date_return, renth_dateend) / 1.07
                    ELSE 0
                END, 2
            ) AS rent_difference
        FROM npd_db.rentorder_head
        WHERE YEAR(renth_date_return) = YEAR(CURDATE())
          AND DATE(renth_date_return) <= CURDATE()
          AND renth_cancel = 'N'
          AND renth_bookingcancel = 'N'
          AND (renth_salename IS NULL OR TRIM(renth_salename) = '')
    ) AS rent_combined
    GROUP BY branchid, report_month
) rent ON mb.branch_id = rent.branchid AND mr.m = rent.report_month

-- ส่วนค้างชำระ (เฉพาะบิลที่ไม่มีเซลล์) แยกตามเดือน
LEFT JOIN (
    SELECT
        o.branchid,
        o.report_month,
        o.outstanding_bill_count,
        o.total_outstanding,
        COALESCE(p.total_paid, 0) AS total_paid
    FROM (
        SELECT
            TRIM(h.branchid) AS branchid,
            MONTH(h.arh_date) AS report_month,
            COUNT(*) AS outstanding_bill_count,
            SUM(
                COALESCE(h.arh_amount, 0)
                + COALESCE(h.arh_vat, 0)
                + COALESCE(h.arh_tax, 0)
                + COALESCE(h.arh_insure, 0)
                + COALESCE(h.arh_lost, 0)
                + COALESCE(h.arh_transport, 0)
            ) AS total_outstanding
        FROM npd_db.ar_head h
        JOIN npd_db.rentorder_head r ON h.arh_docid = r.renth_id
        WHERE h.cancel = 'N'
          AND YEAR(h.arh_date) = YEAR(CURDATE())
          AND h.arh_date <= CURDATE()
          AND (r.renth_salename IS NULL OR TRIM(r.renth_salename) = '')
        GROUP BY TRIM(h.branchid), MONTH(h.arh_date)
    ) o
    LEFT JOIN (
        SELECT
            TRIM(h.branchid) AS branchid,
            MONTH(h.arh_date) AS report_month,
            SUM(
                COALESCE(p.arp_amount, 0)
                + COALESCE(p.arp_vat, 0)
                + COALESCE(p.arp_tax, 0)
                + COALESCE(p.arp_insure, 0)
                + COALESCE(p.arp_lost, 0)
                + COALESCE(p.arp_broken, 0)
                + COALESCE(p.arp_transport, 0)
                + COALESCE(p.arp_fee, 0)
            ) AS total_paid
        FROM npd_db.ar_repay p
        JOIN npd_db.ar_head h ON p.arh_num = h.num
        JOIN npd_db.rentorder_head r ON h.arh_docid = r.renth_id
        WHERE p.cancel = 'N'
          AND h.cancel = 'N'
          AND YEAR(h.arh_date) = YEAR(CURDATE())
          AND h.arh_date <= CURDATE()
          AND YEAR(p.arp_datereceive) = YEAR(CURDATE())
          AND p.arp_datereceive <= CURDATE()
          AND (r.renth_salename IS NULL OR TRIM(r.renth_salename) = '')
          AND MONTH(h.arh_date) = MONTH(p.arp_datereceive)
        GROUP BY TRIM(h.branchid), MONTH(h.arh_date)
    ) p ON o.branchid = p.branchid AND o.report_month = p.report_month
) ar ON mb.branch_id = ar.branchid AND mr.m = ar.report_month

-- ส่วนรับชำระบิลเก่า (เฉพาะบิลที่ไม่มีเซลล์) แยกตามเดือน
LEFT JOIN (
    SELECT
        TRIM(h.branchid) AS branchid,
        MONTH(p.arp_datereceive) AS report_month,
        SUM(
            COALESCE(p.arp_amount, 0)
            + COALESCE(p.arp_vat, 0)
            + COALESCE(p.arp_tax, 0)
            + COALESCE(p.arp_insure, 0)
            + COALESCE(p.arp_lost, 0)
            + COALESCE(p.arp_broken, 0)
            + COALESCE(p.arp_transport, 0)
            + COALESCE(p.arp_fee, 0)
        ) AS old_debt_paid
    FROM npd_db.ar_repay p
    JOIN npd_db.ar_head h ON p.arh_num = h.num
    JOIN npd_db.rentorder_head r ON h.arh_docid = r.renth_id
    WHERE p.cancel = 'N'
      AND h.cancel = 'N'
      AND h.arh_date < DATE(CONCAT(YEAR(CURDATE()), '-01-01'))
      AND YEAR(p.arp_datereceive) = YEAR(CURDATE())
      AND p.arp_datereceive <= CURDATE()
      AND (r.renth_salename IS NULL OR TRIM(r.renth_salename) = '')
    GROUP BY TRIM(h.branchid), MONTH(p.arp_datereceive)
) ar_old ON mb.branch_id = ar_old.branchid AND mr.m = ar_old.report_month

WHERE rent.branchid IS NOT NULL OR ar.branchid IS NOT NULL OR ar_old.branchid IS NOT NULL

UNION ALL

-- ===== ยอดเซลล์แต่ละคน (แยกตามชื่อเซลล์, สาขา, และเดือน) =====
SELECT
    mr.period_label AS report_period,
    'เซลล์' AS report_type,
    sales.branchid AS branch_id,
    sales.branch_name AS branch_name,
    sales.salename AS salesperson_name,
    COALESCE(sales.initial_rent, 0) AS initial_rent,
    COALESCE(sales.discount, 0) AS discount,
    COALESCE(sales.rent_difference, 0) AS rent_difference,
    COALESCE(sales.initial_rent, 0) - COALESCE(sales.discount, 0) + COALESCE(sales.rent_difference, 0) AS total_rent_revenue,
    COALESCE(ar.outstanding_bill_count, 0) AS outstanding_bill_count,
    COALESCE(ar.total_outstanding, 0) AS total_outstanding,
    COALESCE(ar.total_paid, 0) AS total_paid,
    COALESCE(ar.total_outstanding, 0) - COALESCE(ar.total_paid, 0) AS net_outstanding,
    COALESCE(ar_old.old_debt_paid, 0) AS old_debt_paid,
    (COALESCE(sales.initial_rent, 0) - COALESCE(sales.discount, 0) + COALESCE(sales.rent_difference, 0))
    - (COALESCE(ar.total_outstanding, 0) - COALESCE(ar.total_paid, 0))
    + COALESCE(ar_old.old_debt_paid, 0) AS net_total,
    mr.month_start AS report_date_from,
    mr.month_end AS report_date_to

FROM month_range mr
INNER JOIN (
    -- ค่าเช่าแยกตามเซลล์, สาขา, และเดือน
    SELECT
        branchid,
        mb.branch_name,
        TRIM(salename) AS salename,
        report_month,
        SUM(initial_rent) AS initial_rent,
        SUM(discount) AS discount,
        SUM(rent_difference) AS rent_difference
    FROM (
        SELECT
            branchid,
            renth_salename AS salename,
            MONTH(renth_datestart) AS report_month,
            ROUND(renth_rentbegin / 1.07, 2) AS initial_rent,
            0 AS discount,
            0 AS rent_difference
        FROM npd_db.rentorder_head
        WHERE YEAR(renth_datestart) = YEAR(CURDATE())
          AND DATE(renth_datestart) <= CURDATE()
          AND renth_cancel = 'N'
          AND renth_bookingcancel = 'N'
          AND renth_salename IS NOT NULL AND TRIM(renth_salename) != ''

        UNION ALL

        SELECT
            branchid,
            renth_salename AS salename,
            MONTH(renth_date_return) AS report_month,
            0 AS initial_rent,
            ROUND(renth_discount_return / 1.07, 2) AS discount,
            ROUND(
                CASE
                    WHEN DATEDIFF(renth_dateend, renth_datestart) > 0
                    THEN (renth_rentbegin / DATEDIFF(renth_dateend, renth_datestart))
                         * DATEDIFF(renth_date_return, renth_dateend) / 1.07
                    ELSE 0
                END, 2
            ) AS rent_difference
        FROM npd_db.rentorder_head
        WHERE YEAR(renth_date_return) = YEAR(CURDATE())
          AND DATE(renth_date_return) <= CURDATE()
          AND renth_cancel = 'N'
          AND renth_bookingcancel = 'N'
          AND renth_salename IS NOT NULL AND TRIM(renth_salename) != ''
    ) AS rent_combined
    JOIN npd_db.master_branch mb ON rent_combined.branchid = mb.branch_id
    GROUP BY branchid, mb.branch_name, TRIM(salename), report_month
) sales ON mr.m = sales.report_month

-- ส่วนค้างชำระ (แยกตามเซลล์, สาขา, และเดือน)
LEFT JOIN (
    SELECT
        o.branchid,
        o.salename,
        o.report_month,
        o.outstanding_bill_count,
        o.total_outstanding,
        COALESCE(p.total_paid, 0) AS total_paid
    FROM (
        SELECT
            TRIM(h.branchid) AS branchid,
            TRIM(r.renth_salename) AS salename,
            MONTH(h.arh_date) AS report_month,
            COUNT(*) AS outstanding_bill_count,
            SUM(
                COALESCE(h.arh_amount, 0)
                + COALESCE(h.arh_vat, 0)
                + COALESCE(h.arh_tax, 0)
                + COALESCE(h.arh_insure, 0)
                + COALESCE(h.arh_lost, 0)
                + COALESCE(h.arh_transport, 0)
            ) AS total_outstanding
        FROM npd_db.ar_head h
        JOIN npd_db.rentorder_head r ON h.arh_docid = r.renth_id
        WHERE h.cancel = 'N'
          AND YEAR(h.arh_date) = YEAR(CURDATE())
          AND h.arh_date <= CURDATE()
          AND r.renth_salename IS NOT NULL AND TRIM(r.renth_salename) != ''
        GROUP BY TRIM(h.branchid), TRIM(r.renth_salename), MONTH(h.arh_date)
    ) o
    LEFT JOIN (
        SELECT
            TRIM(h.branchid) AS branchid,
            TRIM(r.renth_salename) AS salename,
            MONTH(h.arh_date) AS report_month,
            SUM(
                COALESCE(p.arp_amount, 0)
                + COALESCE(p.arp_vat, 0)
                + COALESCE(p.arp_tax, 0)
                + COALESCE(p.arp_insure, 0)
                + COALESCE(p.arp_lost, 0)
                + COALESCE(p.arp_broken, 0)
                + COALESCE(p.arp_transport, 0)
                + COALESCE(p.arp_fee, 0)
            ) AS total_paid
        FROM npd_db.ar_repay p
        JOIN npd_db.ar_head h ON p.arh_num = h.num
        JOIN npd_db.rentorder_head r ON h.arh_docid = r.renth_id
        WHERE p.cancel = 'N'
          AND h.cancel = 'N'
          AND YEAR(h.arh_date) = YEAR(CURDATE())
          AND h.arh_date <= CURDATE()
          AND YEAR(p.arp_datereceive) = YEAR(CURDATE())
          AND p.arp_datereceive <= CURDATE()
          AND r.renth_salename IS NOT NULL AND TRIM(r.renth_salename) != ''
          AND MONTH(h.arh_date) = MONTH(p.arp_datereceive)
        GROUP BY TRIM(h.branchid), TRIM(r.renth_salename), MONTH(h.arh_date)
    ) p ON o.branchid = p.branchid AND o.salename = p.salename AND o.report_month = p.report_month
) ar ON sales.branchid = ar.branchid AND sales.salename = ar.salename AND mr.m = ar.report_month

-- ส่วนรับชำระบิลเก่า (แยกตามเซลล์, สาขา, และเดือน)
LEFT JOIN (
    SELECT
        TRIM(h.branchid) AS branchid,
        TRIM(r.renth_salename) AS salename,
        MONTH(p.arp_datereceive) AS report_month,
        SUM(
            COALESCE(p.arp_amount, 0)
            + COALESCE(p.arp_vat, 0)
            + COALESCE(p.arp_tax, 0)
            + COALESCE(p.arp_insure, 0)
            + COALESCE(p.arp_lost, 0)
            + COALESCE(p.arp_broken, 0)
            + COALESCE(p.arp_transport, 0)
            + COALESCE(p.arp_fee, 0)
        ) AS old_debt_paid
    FROM npd_db.ar_repay p
    JOIN npd_db.ar_head h ON p.arh_num = h.num
    JOIN npd_db.rentorder_head r ON h.arh_docid = r.renth_id
    WHERE p.cancel = 'N'
      AND h.cancel = 'N'
      AND h.arh_date < DATE(CONCAT(YEAR(CURDATE()), '-01-01'))
      AND YEAR(p.arp_datereceive) = YEAR(CURDATE())
      AND p.arp_datereceive <= CURDATE()
      AND r.renth_salename IS NOT NULL AND TRIM(r.renth_salename) != ''
    GROUP BY TRIM(h.branchid), TRIM(r.renth_salename), MONTH(p.arp_datereceive)
) ar_old ON sales.branchid = ar_old.branchid AND sales.salename = ar_old.salename AND mr.m = ar_old.report_month

ORDER BY branch_id, report_period, report_type, salesperson_name
            """

            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            _logger.info(f"Query returned {len(results)} records")

            # Clear existing data
            self.search([]).sudo().unlink()

            # Create new records
            for row in results:
                salesperson_name = row.get('salesperson_name', '') or ''
                report_type_value = 'branch' if row.get('report_type') == 'สาขา' else 'sales'

                # ค้นหา employee จาก Odoo และดึง x_user_id (เฉพาะประเภทเซลล์)
                employee = None
                employee_code = ''
                if report_type_value == 'sales' and salesperson_name:
                    employee, employee_code = self._get_employee_by_salesperson(salesperson_name)

                # ค้นหารหัสสาขาใน Odoo
                branch_id_odoo = self._get_branch_id_odoo(row.get('branch_name', ''))

                self.create({
                    'report_period': row.get('report_period', ''),
                    'report_type': report_type_value,
                    'branch_id': row.get('branch_id', ''),
                    'branch_id_odoo': branch_id_odoo,
                    'branch_name': row.get('branch_name', ''),
                    'employee_id': employee.id if employee else False,
                    'employee_code': employee_code,
                    'salesperson_name': salesperson_name,
                    'initial_rent': row.get('initial_rent', 0) or 0,
                    'discount': row.get('discount', 0) or 0,
                    'rent_difference': row.get('rent_difference', 0) or 0,
                    'total_rent_revenue': row.get('total_rent_revenue', 0) or 0,
                    'outstanding_bill_count': row.get('outstanding_bill_count', 0) or 0,
                    'total_outstanding': row.get('total_outstanding', 0) or 0,
                    'total_paid': row.get('total_paid', 0) or 0,
                    'net_outstanding': row.get('net_outstanding', 0) or 0,
                    'old_debt_paid': row.get('old_debt_paid', 0) or 0,
                    'net_total': row.get('net_total', 0) or 0,
                    'report_date_from': row.get('report_date_from'),
                    'report_date_to': row.get('report_date_to'),
                })

            _logger.info(f"Successfully created {len(results)} commission records")

        except Exception as e:
            _logger.error(f"Error fetching commission data: {str(e)}")
            raise UserError(f"เกิดข้อผิดพลาดในการดึงข้อมูล: {str(e)}")

        _logger.info("Completed fetch_all_commission_data")


class SalesCommissionReportWizard(models.TransientModel):
    _name = 'npd.sales.commission.report.wizard'
    _description = 'Wizard สำหรับเลือกเดือนและปีรายงาน'

    @api.model
    def _get_month_selection(self):
        """สร้างตัวเลือกเดือน"""
        return [
            ('01', 'มกราคม'),
            ('02', 'กุมภาพันธ์'),
            ('03', 'มีนาคม'),
            ('04', 'เมษายน'),
            ('05', 'พฤษภาคม'),
            ('06', 'มิถุนายน'),
            ('07', 'กรกฎาคม'),
            ('08', 'สิงหาคม'),
            ('09', 'กันยายน'),
            ('10', 'ตุลาคม'),
            ('11', 'พฤศจิกายน'),
            ('12', 'ธันวาคม'),
        ]

    @api.model
    def _get_year_selection(self):
        """สร้างตัวเลือกปี (ปีปัจจุบัน และ 2 ปีย้อนหลัง)"""
        current_year = date.today().year
        return [
            (str(current_year), str(current_year)),
            (str(current_year - 1), str(current_year - 1)),
            (str(current_year - 2), str(current_year - 2)),
        ]

    @api.model
    def _get_branch_selection(self):
        """สร้างตัวเลือกสาขาจากข้อมูลในรายงาน"""
        # ดึงสาขาที่มีในรายงานแทนการดึงจาก res.branch โดยตรง
        reports = self.env['npd.sales.commission.report'].sudo().search([])
        branches = set()
        for r in reports:
            if r.branch_name and r.branch_id_odoo:
                branches.add((r.branch_id_odoo, r.branch_name))

        # เรียงตามชื่อสาขา
        sorted_branches = sorted(list(branches), key=lambda x: x[1])
        return [('', 'ทุกสาขา')] + sorted_branches

    month = fields.Selection(
        selection='_get_month_selection',
        string='เดือน',
        required=True,
        default=lambda self: str(date.today().month).zfill(2)
    )
    year = fields.Selection(
        selection='_get_year_selection',
        string='ปี',
        required=True,
        default=lambda self: str(date.today().year)
    )
    branch_filter = fields.Selection(
        selection='_get_branch_selection',
        string='สาขา',
        default='',
        help='เลือกสาขาที่ต้องการดูรายงาน'
    )
    report_type_filter = fields.Selection([
        ('all', 'ทั้งหมด'),
        ('branch', 'สาขา'),
        ('sales', 'เซลล์')
    ], string='ประเภท', default='all')

    def action_generate_report(self):
        """กรองข้อมูลจาก Odoo ตามเดือน ปี และสาขาที่เลือก"""
        # สร้าง report_period ในรูปแบบ "ปี/เดือน" เช่น "2026/01"
        report_period = f"{self.year}/{self.month}"

        # สร้าง domain ตามตัวกรอง
        domain = [
            ('report_period', '=', report_period),
        ]

        # กรองตามประเภท
        if self.report_type_filter and self.report_type_filter != 'all':
            domain.append(('report_type', '=', self.report_type_filter))

        # กรองตามสาขา (ถ้าเลือก)
        if self.branch_filter:
            domain.append(('branch_id_odoo', '=', self.branch_filter))

        return {
            'type': 'ir.actions.act_window',
            'name': f'รายงานค่าคอมบ้านเขียว - {self.month}/{self.year}',
            'res_model': 'npd.sales.commission.report',
            'view_mode': 'tree,form',
            'domain': domain,
            'target': 'current',
        }
