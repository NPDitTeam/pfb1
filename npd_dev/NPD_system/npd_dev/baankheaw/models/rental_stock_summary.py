# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql


class RentalStockSummary(models.Model):
    _name = 'baankheaw.rental_stock_summary'
    _description = 'Stock เช่า แยกสาขา'
    _order = 'product_id, branch_name'  # เรียงข้อมูลตามรหัสสินค้าและสาขา

    # Fields based on the provided query
    product_id = fields.Char(string='รหัสสินค้า')
    branch_name = fields.Char(string='สาขา')
    product_name = fields.Char(string='ชื่อสินค้า')
    initial_stock = fields.Float(string='สต็อคตั้งต้น', digits=(10, 2))
    stock_in = fields.Float(string='สต็อคเข้า', digits=(10, 2))
    stock_out = fields.Float(string='สต็อคออก', digits=(10, 2))

    def action_update_rental_stock_data(self):
        """Action method for the 'Update' button."""
        self.env['baankheaw.rental_stock_summary'].sudo().fetch_and_store_rental_stock_data()

    @api.model
    def fetch_and_store_rental_stock_data(self):
        """Connects to the external DB, fetches the stock data, and updates the model."""
        try:
            # ใช้ข้อมูลการเชื่อมต่อเดียวกับตัวอย่าง
            conn = pymysql.connect(
                host='150.95.26.61',
                user='greenhome',
                password='NPD@db789',
                database='npd_db',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )

            # คิวรีที่ให้มา
            query = """
                -- 1) สินค้าปกติ
                SELECT
                    sa.sa_pdnid AS 'รหัสสินค้า',
                    mb.branch_name AS 'สาขา',
                    mp.pdn_name AS 'ชื่อสินค้า',
                    sa.sa_firststock AS 'สต็อคตั้งต้น',
                    sa.sa_stockin AS 'สต็อคเข้า',
                    sa.sa_stockout AS 'สต็อคออก'
                FROM npd_db.master_stockactual sa
                LEFT JOIN npd_db.master_branch mb 
                    ON sa.branchid = mb.branch_id
                LEFT JOIN npd_db.master_productname mp 
                    ON sa.sa_pdnid = mp.pdn_id
                WHERE mb.branch_id != '01'
                AND sa.sa_pdnid NOT IN ('10-009','10-006','10-001')

                UNION ALL

                -- 2) 10-009 คำนวณจาก 10-011 ÷ 2
                SELECT
                    '10-009' AS 'รหัสสินค้า',
                    mb.branch_name AS 'สาขา',
                    'นั่งร้าน 0.490 M' AS 'ชื่อสินค้า',
                    ROUND(sa.sa_firststock/2,2) AS 'สต็อคตั้งต้น',
                    ROUND(sa.sa_stockin/2,2) AS 'สต็อคเข้า',
                    ROUND(sa.sa_stockout/2,2) AS 'สต็อคออก'
                FROM npd_db.master_stockactual sa
                LEFT JOIN npd_db.master_branch mb 
                    ON sa.branchid = mb.branch_id
                WHERE mb.branch_id != '01'
                AND sa.sa_pdnid = '10-011'

                UNION ALL

                -- 3) 10-006 คำนวณจาก 10-008 ÷ 2
                SELECT
                    '10-006' AS 'รหัสสินค้า',
                    mb.branch_name AS 'สาขา',
                    'นั่งร้าน 0.914 M' AS 'ชื่อสินค้า',
                    ROUND(sa.sa_firststock/2,2) AS 'สต็อคตั้งต้น',
                    ROUND(sa.sa_stockin/2,2) AS 'สต็อคเข้า',
                    ROUND(sa.sa_stockout/2,2) AS 'สต็อคออก'
                FROM npd_db.master_stockactual sa
                LEFT JOIN npd_db.master_branch mb 
                    ON sa.branchid = mb.branch_id
                WHERE mb.branch_id != '01'
                AND sa.sa_pdnid = '10-008'

                UNION ALL

                -- 4) 10-001 คำนวณจาก 10-003 ÷ 2
                SELECT
                    '10-001' AS 'รหัสสินค้า',
                    mb.branch_name AS 'สาขา',
                    'นั่งร้าน 1.7 M' AS 'ชื่อสินค้า',
                    ROUND(sa.sa_firststock/2,2) AS 'สต็อคตั้งต้น',
                    ROUND(sa.sa_stockin/2,2) AS 'สต็อคเข้า',
                    ROUND(sa.sa_stockout/2,2) AS 'สต็อคออก'
                FROM npd_db.master_stockactual sa
                LEFT JOIN npd_db.master_branch mb 
                    ON sa.branchid = mb.branch_id
                WHERE mb.branch_id != '01'
                AND sa.sa_pdnid = '10-003'

                ORDER BY `รหัสสินค้า`, `สาขา`
            """

            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            # ✅ ลบข้อมูลเก่าทั้งหมดในโมเดลนี้ก่อนสร้างใหม่ เพื่อให้ข้อมูลเป็นปัจจุบันเสมอ
            self.search([]).sudo().unlink()

            # สร้าง records ใหม่จากข้อมูลที่ดึงมา
            for row in results:
                self.create({
                    'product_id': row.get('รหัสสินค้า'),
                    'branch_name': row.get('สาขา'),
                    'product_name': row.get('ชื่อสินค้า'),
                    'initial_stock': row.get('สต็อคตั้งต้น'),
                    'stock_in': row.get('สต็อคเข้า'),
                    'stock_out': row.get('สต็อคออก'),
                })
        except Exception as e:
            raise UserError(f"❌ ดึงข้อมูลไม่สำเร็จ: {str(e)}")