# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql


class ProductStockSummary(models.Model):
    _name = 'baankheaw.product_stock_summary_day'
    _description = 'สรุปสต๊อกต่อสินค้า (รวมทุกสาขา)ตามรอบวัน'
    _order = 'pdn_id'

    # ข้อมูลสินค้า
    pdn_id = fields.Char(string="รหัสสินค้า", index=True)
    product_name = fields.Char(string="รายการสินค้า", index=True)
    branch_list = fields.Text(string="สาขา")  # 🆕 เพิ่มฟิลด์สาขา

    # ราคา/คุณสมบัติ
    price_per_day = fields.Float(string="ค่าเช่า/รายวัน")
    price_per_month = fields.Float(string="ค่าเช่า/รายเดือน")
    guarantee = fields.Float(string="ค่าประกัน")
    lost_price = fields.Float(string="ค่าใช้จ่ายปรับหาย")
    weight = fields.Float(string="น้ำหนัก")

    # ยอดรวมทุกสาขา
    stock_begin_total = fields.Integer(string="ตั้งต้น (รวม)")
    stock_rented_total = fields.Integer(string="ถูกเช่า (รวม)")
    stock_lost_total = fields.Integer(string="ปรับหาย (รวม)")
    stock_remain_total = fields.Integer(string="คงเหลือ (รวม)")

    def action_update_product_summary_day(self):
        """ปุ่มกดใน Odoo เพื่อดึงข้อมูลใหม่"""
        self.sudo().fetch_and_store_product_summary_data_day()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'สำเร็จ',
                'message': 'อัปเดตข้อมูลสรุปสต๊อกเรียบร้อยแล้ว',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def fetch_and_store_product_summary_data_day(self):
        """
        🎯 ดึงข้อมูลจาก MySQL โดยใช้ branch_list และคิวรีเดียวกับ stock_daily_report.py
        แล้วรวมยอดต่อสินค้า พร้อมแสดงรายชื่อสาขา

        📋 ยึดตาม stock_daily_report.py เป็นหลัก
        ✅ ใช้คิวรีเดียวกันทุกตัว
        ✅ รวมยอดต่อสินค้าทุกสาขา
        ✅ เก็บรายชื่อสาขาที่มีสินค้า
        """
        conn = None
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

            # 🔹 ใช้ branch_list เดียวกันกับ stock_daily_report.py
            branch_list = [
                '02', '04', '05', '06', '07', '08', '09', '12', '13',
                '15', '16', '17', '19', '20', '21', '22', '23', '24',
                '25', '26', '27', '28', '29'
            ]

            # 📦 Dictionary เก็บข้อมูลระดับ branch + product (เหมือน stock_daily_report.py)
            data_dict = {}

            # 📦 Dictionary เก็บยอดรวมต่อสินค้า
            product_summary = {}

            # ลูปทุก branch_id (เหมือน stock_daily_report.py)
            for branch_id in branch_list:

                # ==========================================
                # Query 1: สินค้าตั้งต้น (เหมือน stock_daily_report.py 100%)
                # ==========================================
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
                        'pdn_id': row['pdn_id'],
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

                # ==========================================
                # Query 2: สินค้าที่ถูกเช่า (เหมือน stock_daily_report.py 100%)
                # ==========================================
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

                # ==========================================
                # Query 3: สินค้าที่ปรับหาย (เหมือน stock_daily_report.py 100%)
                # ==========================================
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

            # ==========================================
            # 🧮 คำนวณสินค้าคงเหลือและรวมยอดต่อสินค้า
            # ==========================================
            for key, data in data_dict.items():
                # คำนวณคงเหลือแต่ละสาขา
                data['stock_remain'] = data['stock_begin'] - data['stock_rented'] - data['stock_lost']

                pdn_id = data['pdn_id']

                # สร้าง entry ในสรุปสินค้าถ้ายังไม่มี
                if pdn_id not in product_summary:
                    product_summary[pdn_id] = {
                        'pdn_id': pdn_id,
                        'product_name': data['product_name'],
                        'price_per_day': data['price_per_day'],
                        'price_per_month': data['price_per_month'],
                        'guarantee': data['guarantee'],
                        'lost_price': data['lost_price'],
                        'weight': data['weight'],
                        'stock_begin_total': 0,
                        'stock_rented_total': 0,
                        'stock_lost_total': 0,
                        'stock_remain_total': 0,
                        'branches': set()  # 🆕 เก็บชื่อสาขา
                    }

                # รวมยอดต่อสินค้า
                product_summary[pdn_id]['stock_begin_total'] += data['stock_begin']
                product_summary[pdn_id]['stock_rented_total'] += data['stock_rented']
                product_summary[pdn_id]['stock_lost_total'] += data['stock_lost']
                product_summary[pdn_id]['stock_remain_total'] += data['stock_remain']

                # 🆕 เพิ่มชื่อสาขา
                product_summary[pdn_id]['branches'].add(data['branch_name'])

            # ==========================================
            # 💾 บันทึกข้อมูลลง Odoo (Insert เฉพาะข้อมูลใหม่)
            # ==========================================

            for pdn_id, summary in product_summary.items():
                # ค้นหา record ที่มี pdn_id นี้อยู่แล้ว
                existing_record = self.search([('pdn_id', '=', pdn_id)], limit=1)

                # ✅ ถ้ามีอยู่แล้ว -> ข้าม (ไม่ update)
                if existing_record:
                    continue

                # ✅ ถ้าไม่มี -> Create ใหม่
                branch_names = ', '.join(sorted(summary['branches']))

                self.create({
                    'pdn_id': summary['pdn_id'],
                    'product_name': summary['product_name'],
                    'branch_list': branch_names,
                    'price_per_day': summary['price_per_day'],
                    'price_per_month': summary['price_per_month'],
                    'guarantee': summary['guarantee'],
                    'lost_price': summary['lost_price'],
                    'weight': summary['weight'],
                    'stock_begin_total': summary['stock_begin_total'],
                    'stock_rented_total': summary['stock_rented_total'],
                    'stock_lost_total': summary['stock_lost_total'],
                    'stock_remain_total': summary['stock_remain_total'],
                })

        except pymysql.Error as e:
            raise UserError(f"❌ เชื่อมต่อฐานข้อมูลไม่สำเร็จ: {str(e)}")
        except Exception as e:
            raise UserError(f"❌ อัปเดตสรุปสินค้าไม่สำเร็จ: {str(e)}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass