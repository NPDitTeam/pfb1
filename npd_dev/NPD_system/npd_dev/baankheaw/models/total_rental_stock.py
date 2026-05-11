# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql

class TotalRentalStock(models.Model):
    _name = 'baankheaw.total_rental_stock'
    _description = 'Stock เช่ารวม'
    _order = 'product_code' # เรียงข้อมูลตามรหัสสินค้า

    # Fields based on the provided query
    product_code = fields.Char(string='รหัสสินค้า')
    product_name = fields.Char(string='ชื่อสินค้า')
    total_initial_stock = fields.Float(string='รวมสต็อคตั้งต้น', digits=(10, 2))
    total_stock_in = fields.Float(string='รวมสต็อคเข้า', digits=(10, 2))
    total_stock_out = fields.Float(string='รวมสต็อคออก', digits=(10, 2))

    def action_update_total_stock_data(self):
        """Action method for the 'Update' button."""
        self.env['baankheaw.total_rental_stock'].sudo().fetch_and_store_total_stock_data()

    @api.model
    def fetch_and_store_total_stock_data(self):
        """Connects to the external DB, fetches the total stock data, and updates the model."""
        try:
            conn = pymysql.connect(
                host='150.95.26.61',
                user='greenhome',
                password='NPD@db789',
                database='npd_db',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )

            # คิวรีสำหรับ Stock เช่ารวม
            query = """
                SELECT 
                    mp.pdn_id AS product_code,
                    mp.pdn_name AS product_name,
                    ROUND(SUM(sa.sa_firststock),2) AS `รวมสต็อคตั้งต้น`,
                    ROUND(SUM(sa.sa_stockin),2) AS `รวมสต็อคเข้า`,
                    ROUND(SUM(sa.sa_stockout),2) AS `รวมสต็อคออก`
                FROM npd_db.master_stockactual sa
                JOIN npd_db.master_productname mp 
                    ON sa.sa_pdnid = mp.pdn_id
                WHERE mp.pdn_id NOT IN ('10-009','10-006','10-001')
                GROUP BY mp.pdn_id, mp.pdn_name

                UNION ALL

                SELECT 
                    '10-009' AS product_code,
                    'นั่งร้าน 0.490 M' AS product_name,
                    ROUND(SUM(sa.sa_firststock)/2,2),
                    ROUND(SUM(sa.sa_stockin)/2,2),
                    ROUND(SUM(sa.sa_stockout)/2,2)
                FROM npd_db.master_stockactual sa
                WHERE sa.sa_pdnid = '10-011'

                UNION ALL

                SELECT 
                    '10-006' AS product_code,
                    'นั่งร้าน 0.914 M' AS product_name,
                    ROUND(SUM(sa.sa_firststock)/2,2),
                    ROUND(SUM(sa.sa_stockin)/2,2),
                    ROUND(SUM(sa.sa_stockout)/2,2)
                FROM npd_db.master_stockactual sa
                WHERE sa.sa_pdnid = '10-008'

                UNION ALL

                SELECT 
                    '10-001' AS product_code,
                    'นั่งร้าน 1.7 M' AS product_name,
                    ROUND(SUM(sa.sa_firststock)/2,2),
                    ROUND(SUM(sa.sa_stockin)/2,2),
                    ROUND(SUM(sa.sa_stockout)/2,2)
                FROM npd_db.master_stockactual sa
                WHERE sa.sa_pdnid = '10-003'

                ORDER BY product_code
            """

            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            # ลบข้อมูลเก่าทั้งหมดก่อนสร้างใหม่
            self.search([]).sudo().unlink()

            for row in results:
                self.create({
                    'product_code': row.get('product_code'),
                    'product_name': row.get('product_name'),
                    'total_initial_stock': row.get('รวมสต็อคตั้งต้น'),
                    'total_stock_in': row.get('รวมสต็อคเข้า'),
                    'total_stock_out': row.get('รวมสต็อคออก'),
                })
        except Exception as e:
            raise UserError(f"❌ ดึงข้อมูลไม่สำเร็จ: {str(e)}")