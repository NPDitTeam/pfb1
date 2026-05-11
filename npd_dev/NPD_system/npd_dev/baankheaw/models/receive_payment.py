# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql
import logging

_logger = logging.getLogger(__name__)


class ReceivePayment(models.Model):
    _name = 'baankheaw.receive_payment'
    _description = 'รับชำระ'
    _order = 'arp_docid desc'

    # ===== ฟิลด์ตามคิวรี (พร้อมชื่อภาษาไทยใน string=) =====
    arp_docid = fields.Char(string='เลขที่เอกสารอ้างอิง')
    arp_datereceive = fields.Date(string='วันที่รับชำระ')
    arp_amount = fields.Float(string='ยอดค่าเช่า', digits=(16, 2))
    arp_vat = fields.Float(string='ภาษีมูลค่าเพิ่ม', digits=(16, 2))
    arp_tax = fields.Float(string='ภาษีหัก ณ ที่จ่าย', digits=(16, 2))
    arp_insure = fields.Float(string='ค่ามัดจำ/ประกัน', digits=(16, 2))
    arp_lost = fields.Float(string='ค่าปรับสินค้าหาย', digits=(16, 2))
    arp_broken = fields.Float(string='ค่าปรับสินค้าชำรุด', digits=(16, 2))
    arp_transport = fields.Float(string='ค่าขนส่ง', digits=(16, 2))
    arp_fee = fields.Float(string='ค่าธรรมเนียมอื่นๆ', digits=(16, 2))

    total_all = fields.Float(string='ยอดรวมทั้งหมด', digits=(16, 2))
    arp_remark = fields.Char(string='หมายเหตุ')
    arp_type = fields.Char(string='ประเภทเอกสาร')
    dateissue = fields.Date(string='วันที่ออกบิล')
    cus_id = fields.Char(string='รหัสลูกค้า')
    branch_name = fields.Char(string='สาขา')
    cus_fullname = fields.Char(string='ลูกค้า')
    cus_cpnname = fields.Char(string='บริษัท')
    cus_tel = fields.Char(string='เบอร์ลูกค้า')
    renth_customerincome = fields.Char(string='ผู้รับผิดชอบ')
    renth_salename = fields.Char(string='ชื่อพนักงานขาย')

    # ===== ฟิลด์ใหม่: ข้อมูลพนักงานออกบิล =====
    userissue = fields.Char(string='รหัสพนักงานออกบิล')
    emp_nickname = fields.Char(string='ชื่อเล่นพนักงาน')
    emp_fullname = fields.Char(string='ชื่อจริงพนักงาน')

    # ===== ปุ่มอัปเดตจากฐานภายนอก =====
    def action_update_receive_payment(self):
        self.env['baankheaw.receive_payment'].sudo().fetch_and_store_receive_payment()

    @api.model
    def fetch_and_store_receive_payment(self):
        """ดึงข้อมูลตามคิวรีและบันทึกเข้าโมเดลนี้"""
        try:
            conn = pymysql.connect(
                host='150.95.26.61',
                user='greenhome',
                password='NPD@db789',
                database='npd_db',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            query = """
                SELECT 
                    p.arp_docid,
                    p.arp_datereceive,
                    p.arp_amount,
                    p.arp_vat,
                    p.arp_tax,
                    p.arp_insure,
                    p.arp_lost,
                    p.arp_broken,
                    p.arp_transport,
                    p.arp_fee,
                    (p.arp_amount 
                       + COALESCE(p.arp_vat, 0) 
                       + COALESCE(p.arp_tax, 0) 
                       + COALESCE(p.arp_insure, 0) 
                       + COALESCE(p.arp_lost, 0) 
                       + COALESCE(p.arp_broken, 0) 
                       + COALESCE(p.arp_transport, 0) 
                       + COALESCE(p.arp_fee, 0)
                    ) AS total_all,
                    p.arp_remark,
                    p.arp_type,
                    p.dateissue,
                    b.branch_name AS branch_name,
                    c.cus_fullname AS cus_fullname,
                    c.cus_cpnname AS cus_cpnname,
                    c.cus_tel AS cus_tel,
                    c.cus_id AS cus_id,
                    rh.renth_customerincome AS renth_customerincome,
                    rh.renth_salename AS renth_salename,
                    p.userissue,
                    e.emp_nickname AS emp_nickname,
                    CONCAT(e.emp_name,' ',e.emp_surname) AS emp_fullname
                FROM npd_db.ar_repay p
                JOIN npd_db.master_customer c ON TRIM(p.arp_cusid) = TRIM(c.cus_id)
                JOIN npd_db.master_branch b ON TRIM(p.branchid) = TRIM(b.branch_id)
                LEFT JOIN npd_db.rentorder_head rh ON TRIM(rh.renth_id) = TRIM(p.arp_docid)
                LEFT JOIN npd_db.master_employee e ON TRIM(p.userissue) = TRIM(e.emp_id)
                WHERE p.dateissue >= '2025-10-01' AND p.cancel = 'N'
            """
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            conn.close()

            # เคลียร์ข้อมูลเดิมก่อนโหลดใหม่
            self.search([]).sudo().unlink()

            # สร้างระเบียนใหม่
            for r in rows:
                self.create({
                    'arp_docid': r.get('arp_docid'),
                    'arp_datereceive': r.get('arp_datereceive'),
                    'arp_amount': r.get('arp_amount') or 0.0,
                    'arp_vat': r.get('arp_vat') or 0.0,
                    'arp_tax': r.get('arp_tax') or 0.0,
                    'arp_insure': r.get('arp_insure') or 0.0,
                    'arp_lost': r.get('arp_lost') or 0.0,
                    'arp_broken': r.get('arp_broken') or 0.0,
                    'arp_transport': r.get('arp_transport') or 0.0,
                    'arp_fee': r.get('arp_fee') or 0.0,
                    'total_all': r.get('total_all') or 0.0,
                    'arp_remark': r.get('arp_remark'),
                    'arp_type': r.get('arp_type'),
                    'dateissue': r.get('dateissue'),
                    'branch_name': r.get('branch_name'),
                    'cus_fullname': r.get('cus_fullname'),
                    'cus_cpnname': r.get('cus_cpnname'),
                    'cus_tel': r.get('cus_tel'),
                    'cus_id': r.get('cus_id'),
                    'renth_customerincome': r.get('renth_customerincome'),
                    'renth_salename': r.get('renth_salename'),
                    'userissue': r.get('userissue'),
                    'emp_nickname': r.get('emp_nickname'),
                    'emp_fullname': r.get('emp_fullname'),
                })
        except Exception as e:
            raise UserError(f"❌ ดึงข้อมูลรับชำระไม่สำเร็จ: {str(e)}")