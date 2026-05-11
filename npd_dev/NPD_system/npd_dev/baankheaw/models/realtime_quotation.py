# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql
import datetime


class RentalBillSummary(models.Model):
    _name = 'baankheaw.rental_bill_summary'
    _description = 'ใบบิลเช่า'

    # Fields from the combined SQL queries
    renth_date = fields.Date(string='วันที่เอกสาร') # map to dateissue
    branch_name = fields.Char(string='สาขา') # map to branch_name
    renth_cusid = fields.Char(string='รหัสลูกค้า') # map to renth_cusid (from rh)
    cus_name = fields.Char(string='ชื่อลูกค้า') # map to mc.cus_fullname as name
    name = fields.Char(string='ผู้บันทึก') # map to CONCAT(me.emp_name, ' ', me.emp_surname) AS name
    emp_nickname = fields.Char(string='ชื่อเล่นผู้บันทึก') # map to emp_nickname
    renth_remark = fields.Char(string='หมายเหตุเอกสาร') # map to renth_remark
    renth_date_return = fields.Date(string='วันที่คืน') # map to renth_date_return

    # New Fields from the Odoo14 query
    renth_id = fields.Char(string='ID เอกสารเช่า', index=True, readonly=True) # map to rh.renth_id, changed to Char
    renth_sitelocation = fields.Char(string='สถานที่ติดตั้ง') # map to renth_sitelocation
    renth_datestart = fields.Date(string='วันที่เริ่มเช่า') # map to renth_datestart
    renth_dateend = fields.Date(string='วันที่สิ้นสุดเช่า') # map to renth_dateend
    renth_rentbegin = fields.Float(string='ค่าเช่าเริ่มต้น') # map to ค่าเช่าเริ่มต้น
    renth_insure = fields.Float(string='ค่าประกัน') # map to renth_insure
    renth_transport = fields.Float(string='ค่าขนส่ง') # map to renth_transport
    renth_discount_return = fields.Float(string='ส่วนลด') # map to ส่วนลด
    renth_rentactual_return = fields.Float(string='ค่าเช่าจริง') # map to ค่าเช่าจริง
    renth_customerincome = fields.Char(string='ช่องทางการติดต่อ') # map to ช่องทาง
    renth_salename = fields.Char(string='ชื่อเซลล์') # map to ชื่อเซลล์
    renth_dowhat = fields.Char(string='วัตถุประสงค์') # map to วัตถุประสงค์
    cus_cpnname = fields.Char(string='ชื่อบริษัทลูกค้า') # map to cus_cpnname
    cus_cpntaxid = fields.Char(string='เลขประจำตัวผู้เสียภาษี') # map to cus_cpntaxid
    cus_cpnadd = fields.Char(string='ที่อยู่บริษัท') # map to cus_cpnadd
    cus_cpntel = fields.Char(string='เบอร์โทรศัพท์บริษัท') # map to cus_cpntel
    product_list = fields.Text(string='รายการสินค้า', readonly=True) # map to รายการสินค้า (GROUP_CONCAT)

    def action_update_realtime_rental_bill_data(self):
        self.env['baankheaw.rental_bill_summary'].sudo().fetch_and_store_realtime_data()

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

            # Get the current year and format the start date of the year
            current_year = datetime.date.today().year
            start_of_year = f'{current_year}-01-01'
            print("......................................",start_of_year)
            # start_of_year ='2025-06-01'
            # --- New Odoo 14 Query ---
            query = f"""
            SELECT
                rh.renth_id,
                rh.renth_cusid,
                rh.renth_sitelocation,
                rh.renth_datestart,
                rh.renth_dateend,
                rh.renth_date_return,
                rh.renth_remark,
                rh.renth_rentbegin as 'ค่าเช่าเริ่มต้น',
                rh.renth_insure,
                rh.renth_transport,
                rh.renth_discount_return as 'ส่วนลด',
                rh.renth_rentactual_return as "ค่าเช่าจริง",
                rh.renth_customerincome as 'ช่องทาง',
                rh.renth_salename as 'ชื่อเซลล์',
                rh.renth_dowhat as 'วัตถุประสงค์',
                mb.branch_name,
                CONCAT(me.emp_name, ' ', me.emp_surname) AS name,
                me.emp_nickname,
                mc.cus_fullname as cus_name,
                mc.cus_cpnname,
                mc.cus_cpntaxid,
                mc.cus_cpnadd,
                mc.cus_cpntel,
                rh.dateissue as renth_date,
                GROUP_CONCAT(
                    CONCAT(rd.rentd_proname, ' (จำนวน: ', rd.rentd_amount, ')')
                    SEPARATOR ', '
                ) AS 'รายการสินค้า'
            FROM npd_db.rentorder_head rh
            LEFT JOIN npd_db.master_branch mb
                ON rh.branchid = mb.branch_id
            LEFT JOIN npd_db.master_employee me
                ON rh.userissue = me.emp_id
            LEFT JOIN npd_db.master_customer mc
                ON rh.renth_cusid = mc.cus_id
            LEFT JOIN npd_db.rentorder_detail rd
                ON rd.rentd_id = rh.renth_id /* ✅ แก้ไขให้ใช้ rd.rentd_id ตามคิวรีตั้งต้นของคุณ */
            WHERE rh.renth_cancel = 'N'
              AND rh.renth_bookingcancel = 'N'
              AND rh.dateissue >= '{start_of_year}'
            GROUP BY rh.renth_id
            """
            # ---------------------------

            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            # ลบเฉพาะข้อมูลที่มีวันที่เอกสารในปีปัจจุบัน
            self.search([('renth_date', '>=', start_of_year)]).sudo().unlink()

            for row in results:
                self.create({
                    # แปลงเป็น str() เพื่อให้สอดคล้องกับ fields.Char
                    'renth_id': str(row.get('renth_id')) if row.get('renth_id') is not None else False,
                    'renth_date': row.get('renth_date'),
                    'branch_name': row.get('branch_name'),
                    'renth_cusid': row.get('renth_cusid'),
                    'cus_name': row.get('cus_name'),
                    'name': row.get('name'),
                    'emp_nickname': row.get('emp_nickname'),
                    'renth_remark': row.get('renth_remark'),
                    'renth_date_return': row.get('renth_date_return'),
                    # New Fields
                    'renth_sitelocation': row.get('renth_sitelocation'),
                    'renth_datestart': row.get('renth_datestart'),
                    'renth_dateend': row.get('renth_dateend'),
                    'renth_rentbegin': row.get('ค่าเช่าเริ่มต้น'),
                    'renth_insure': row.get('renth_insure'),
                    'renth_transport': row.get('ค่าขนส่ง'),
                    'renth_discount_return': row.get('ส่วนลด'),
                    'renth_rentactual_return': row.get('ค่าเช่าจริง'),
                    'renth_customerincome': row.get('ช่องทาง'),
                    'renth_salename': row.get('ชื่อเซลล์'),
                    'renth_dowhat': row.get('วัตถุประสงค์'),
                    'cus_cpnname': row.get('cus_cpnname'),
                    'cus_cpntaxid': row.get('cus_cpntaxid'),
                    'cus_cpnadd': row.get('cus_cpnadd'),
                    'cus_cpntel': row.get('cus_cpntel'),
                    'product_list': row.get('รายการสินค้า'),
                })
        except Exception as e:
            raise UserError(f"❌ ดึงข้อมูลไม่สำเร็จ: {str(e)}")