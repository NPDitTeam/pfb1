# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql


class StockDailyReport(models.Model):
    _name = 'baankheaw.stock_daily_report'
    _description = 'รายงานสต๊อคประจำวัน'

    branch_name = fields.Char(string="สาขา")
    product_name = fields.Char(string="รายการสินค้า")
    stock_begin = fields.Integer(string="สินค้าตั้งต้น")
    stock_remain = fields.Integer(string="สินค้าคงเหลือ")
    stock_rented = fields.Integer(string="สินค้าที่ถูกเช่า")
    stock_lost = fields.Integer(string="สินค้าที่ปรับหาย")
    price_per_day = fields.Float(string="ค่าเช่า/รายวัน")
    price_per_month = fields.Float(string="ค่าเช่า/รายเดือน")
    guarantee = fields.Float(string="ค่าประกัน")
    lost_price = fields.Float(string="ค่าใช้จ่ายปรับหาย")
    weight = fields.Float(string="น้ำหนัก")

    def action_update_stock_report(self):
        """ปุ่มกดใน Odoo เพื่อดึงข้อมูลใหม่"""
        self.sudo().fetch_and_store_stock_report_data()

    @api.model
    def fetch_and_store_stock_report_data(self):
        try:
            conn = pymysql.connect(
                host='150.95.26.61',
                user='greenhome',
                password='NPD@db789',
                database='npd_db',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = conn.cursor()

            # 🔹 กำหนด branchid ที่ต้องการ loop
            branch_list = [
                '02','04','05','06','07','08','09','12','13',
                '15','16','17','19','20','21','22','23','24',
                '25','26','27','28','29'
            ]

            data_dict = {}

            # ลูปทุก branchid
            for branch_id in branch_list:

                # Query 1: สินค้าตั้งต้น
                query_begin = """
                    SELECT
                        master_branch.branch_name,
                        master_productname.pdn_id,
                        master_productname.pdn_name,
                        master_stockactual.sa_firststock,
                        master_productprice.pp_day,
                        master_productprice.pp_month,
                        master_productprice.pp_insure,
                        master_productprice.pp_lost,
                        master_productname.pdn_weight
                    FROM master_stockactual
                    INNER JOIN master_productname 
                        ON master_stockactual.sa_pdnid = master_productname.pdn_id
                    INNER JOIN master_branch 
                        ON master_stockactual.branchid = master_branch.branch_id
                    INNER JOIN master_productprice 
                        ON master_stockactual.sa_pdnid = master_productprice.pp_pdid
                    WHERE master_stockactual.sa_cancel = 'N'
                      AND master_stockactual.branchid = %s
                      AND master_productprice.branchid = %s
                      AND master_branch.branch_id <> '01'
                    ORDER BY master_productname.pdn_id;
                """
                cursor.execute(query_begin, (branch_id, branch_id))
                results_begin = cursor.fetchall()

                for row in results_begin:
                    key = (branch_id, row['pdn_id'])
                    data_dict[key] = {
                        'branch_name': row['branch_name'],
                        'product_name': row['pdn_name'],
                        'stock_begin': row['sa_firststock'] or 0,
                        'price_per_day': row['pp_day'] or 0.0,
                        'price_per_month': row['pp_month'] or 0.0,
                        'guarantee': row['pp_insure'] or 0.0,
                        'lost_price': row['pp_lost'] or 0.0,
                        'weight': row['pdn_weight'] or 0.0,
                        'stock_rented': 0,
                        'stock_lost': 0,
                        'stock_remain': 0
                    }

                # Query 2: สินค้าที่ถูกเช่า
                query_rented = """
                    SELECT rentorder_detail.rentd_proid,
                           SUM(rentorder_detail.rentd_amount) AS total_rented
                    FROM rentorder_detail
                    JOIN rentorder_head 
                        ON rentorder_head.renth_id = rentorder_detail.rentd_id
                    WHERE rentorder_head.branchid = %s
                      AND rentorder_head.renth_return = 'N'
                      AND rentorder_head.renth_cancel = 'N'
                    GROUP BY rentorder_detail.rentd_proid;
                """
                cursor.execute(query_rented, (branch_id,))
                results_rented = cursor.fetchall()
                for r in results_rented:
                    key = (branch_id, r['rentd_proid'])
                    if key in data_dict:
                        data_dict[key]['stock_rented'] = r['total_rented'] or 0

                # Query 3: สินค้าที่ปรับหาย
                query_lost = """
                    SELECT rentorder_detail.rentd_proid,
                           SUM(rentorder_detail.rentd_amount - rentorder_detail.rentd_amt_return) AS total_lost
                    FROM rentorder_detail
                    JOIN rentorder_head 
                        ON rentorder_head.renth_id = rentorder_detail.rentd_id
                    WHERE rentorder_head.branchid = %s
                      AND rentd_amount <> rentd_amt_return
                      AND rentd_amt_return < rentd_amount
                      AND rentorder_head.renth_return = 'Y'
                      AND rentorder_head.renth_cancel = 'N'
                      AND YEAR(rentorder_head.renth_date_return) >= '2019'
                    GROUP BY rentorder_detail.rentd_proid;
                """
                cursor.execute(query_lost, (branch_id,))
                results_lost = cursor.fetchall()
                for l in results_lost:
                    key = (branch_id, l['rentd_proid'])
                    if key in data_dict:
                        data_dict[key]['stock_lost'] = l['total_lost'] or 0

            conn.close()

            # คำนวณสินค้าคงเหลือ
            for key, data in data_dict.items():
                data['stock_remain'] = data['stock_begin'] - data['stock_rented'] - data['stock_lost']

            # ลบข้อมูลเก่าออกก่อน
            self.search([]).unlink()

            # สร้างข้อมูลใหม่
            for data in data_dict.values():
                self.create(data)

        except Exception as e:
            raise UserError(f"❌ ดึงข้อมูลไม่สำเร็จ: {str(e)}")
