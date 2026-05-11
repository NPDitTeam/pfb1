# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql


class RentalQuotation(models.Model):
    _name = 'baankheaw.rental_quotation'
    _description = 'ใบเสนอราคาเช่า'
    _order = 'dateissue desc, q_id desc'

    # ===== Fields (ตรงกับคิวรีที่กำหนด) =====
    branch_name = fields.Char(string='สาขา')
    q_id = fields.Char(string='เลขที่ใบเสนอราคา', index=True)
    q_cusname = fields.Char(string='ชื่อลูกค้า (จากใบเสนอราคา)')
    q_mobile = fields.Char(string='มือถือ (จากใบเสนอราคา)')
    q_site = fields.Char(string='หน้างาน/ไซต์')
    q_remark = fields.Text(string='หมายเหตุ')
    q_amount = fields.Float(string='ยอดรวม', digits=(12, 2))
    q_insure = fields.Float(string='เงินประกัน', digits=(12, 2))
    q_discountinsure = fields.Float(string='ส่วนลดเงินประกัน', digits=(12, 2))
    q_days = fields.Integer(string='จำนวนวันเช่า')
    userissue = fields.Char(string='รหัสผู้ออกใบเสนอราคา', index=True)
    dateissue = fields.Date(string='วันที่ออกเอกสาร', index=True)
    emp_nickname = fields.Char(string='ชื่อเล่นพนักงาน')
    emp_name = fields.Char(string='ชื่อพนักงาน')
    cus_fullname = fields.Char(string='ชื่อลูกค้า (master)')
    cus_address = fields.Char(string='ที่อยู่ลูกค้า')
    cus_tel = fields.Char(string='โทรลูกค้า')
    cus_cpnname = fields.Char(string='ชื่อบริษัทลูกค้า')
    cus_cpntel = fields.Char(string='โทรบริษัทลูกค้า')

    # ===== ปุ่มดึงข้อมูล =====
    def action_update_rental_quotation(self):
        """กดปุ่มบนฟอร์มหรือในลิสต์ เพื่อดึงข้อมูลล่าสุดจากฐานภายนอก"""
        self.sudo().fetch_and_store_rental_quotation()

    # ===== อ่านค่าการเชื่อมต่อจาก System Parameters (ถูกลบออกและแทนที่ด้วยค่าคงที่) =====
    # @api.model
    # def _get_ext_db_conf(self):
    #     ... (ลบออก) ...

    # ===== ดึงข้อมูลตามคิวรีที่ผู้ใช้ระบุ (เป๊ะ 1:1) =====
    @api.model
    def fetch_and_store_rental_quotation(self):
        # host, user, password, database = self._get_ext_db_conf()  # ลบการเรียกใช้

        # ***** ใช้ค่าการเชื่อมต่อที่ผู้ใช้กำหนด *****
        host = '150.95.26.61'
        user = 'greenhome'
        password = 'NPD@db789'
        database = 'npd_db'
        # *****************************************

        query = """
SELECT 
    mb.branch_name,
    q.q_id,
    q.q_cusname,
    q.q_mobile,
    q.q_site,
    q.q_remark,
    q.q_amount,
    q.q_insure,
    q.q_discountinsure,
    q.q_days,
    q.userissue,
    q.dateissue,
    me.emp_nickname,
    me.emp_name,
    COALESCE(mc.cus_fullname, '-') AS cus_fullname,
    COALESCE(mc.cus_address, '-') AS cus_address,
    COALESCE(mc.cus_tel, '-') AS cus_tel,
    COALESCE(mc.cus_cpnname, '-') AS cus_cpnname,
    COALESCE(mc.cus_cpntel, '-') AS cus_cpntel
FROM npd_db.quotation_head q 
INNER JOIN npd_db.master_branch mb 
    ON mb.branch_id = q.branchid
INNER JOIN npd_db.master_employee me 
    ON me.emp_id = q.userissue
LEFT JOIN npd_db.master_customer mc   -- เปลี่ยนเป็น LEFT JOIN
    ON mc.cus_id = q.q_cusid
WHERE q.dateissue >= '2025-10-01';
        """

        try:
            conn = pymysql.connect(
                host=host, user=user, password=password, database=database,
                charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
            )
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
            conn.close()

            # กลยุทธ์ Clear & Fill: ลบเก่า เติมใหม่ ให้ผู้ใช้ได้ข้อมูลล่าสุดเสมอ
            self.search([]).sudo().unlink()
            for r in rows:
                self.create({
                    'branch_name': r.get('branch_name'),
                    'q_id': r.get('q_id'),
                    'q_cusname': r.get('q_cusname'),
                    'q_mobile': r.get('q_mobile'),
                    'q_site': r.get('q_site'),
                    'q_remark': r.get('q_remark'),
                    'q_amount': r.get('q_amount'),
                    'q_insure': r.get('q_insure'),
                    'q_discountinsure': r.get('q_discountinsure'),
                    'q_days': r.get('q_days'),
                    'userissue': r.get('userissue'),
                    'dateissue': r.get('dateissue'),
                    'emp_nickname': r.get('emp_nickname'),
                    'emp_name': r.get('emp_name'),
                    'cus_fullname': r.get('cus_fullname'),
                    'cus_address': r.get('cus_address'),
                    'cus_tel': r.get('cus_tel'),
                    'cus_cpnname': r.get('cus_cpnname'),
                    'cus_cpntel': r.get('cus_cpntel'),
                })
        except Exception as e:
            raise UserError('❌ ดึงข้อมูลใบเสนอราคาเช่าไม่สำเร็จ: %s' % str(e))