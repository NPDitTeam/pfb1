# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql


class RentalInvoiceReceipt(models.Model):
    _name = 'baankheaw.rental_invoice_receipt'
    _description = 'ใบเสร็จใบกำกับเช่า'
    _order = 'dateissue desc, inv_no desc'  # เรียงข้อมูลตามวันที่ออกและเลขที่ใบเสร็จ

    # Fields based on the provided query
    inv_no = fields.Char(string='เลขที่ใบเสร็จ/กำกับ', readonly=True)
    dateissue = fields.Date(string='วันที่ออก', readonly=True)
    inv_rentid = fields.Char(string='รหัสเช่า', readonly=True)
    branch_name = fields.Char(string='ชื่อสาขา', readonly=True)
    cus_fullname = fields.Char(string='ชื่อลูกค้า', readonly=True)
    cus_cpnname = fields.Char(string='ชื่อบริษัท', readonly=True)
    cus_cpntaxid = fields.Char(string='เลขประจำตัวผู้เสียภาษี', readonly=True)
    cus_cpnadd = fields.Char(string='ที่อยู่บริษัท', readonly=True)
    cus_cpntel = fields.Char(string='เบอร์โทรบริษัท', readonly=True)
    rent_perday = fields.Float(string='ค่าเช่าต่อวัน', digits=(10, 2), readonly=True)
    inv_days = fields.Integer(string='จำนวนวันเช่า', readonly=True)
    inv_statustax = fields.Char(string='สถานะภาษี', readonly=True)
    rent_amount = fields.Float(string='รวมค่าเช่า', digits=(10, 2), compute='_compute_rent_amount', store=True,
                               readonly=True)

    # NEW FIELD: ผู้สร้างใบเสร็จ (Full Name + Nickname)
    full_create = fields.Char(string='ผู้สร้างใบเสร็จ', readonly=True)

    @api.depends('rent_perday', 'inv_days')
    def _compute_rent_amount(self):
        for record in self:
            record.rent_amount = record.rent_perday * record.inv_days

    def action_update_rental_invoice_data(self):
        """Action method for the 'Update' button."""
        self.env['baankheaw.rental_invoice_receipt'].sudo().fetch_and_store_rental_invoice_data()

    @api.model
    def fetch_and_store_rental_invoice_data(self):
        """Connects to the external DB, fetches the rental invoice data, and updates the model."""
        try:
            conn = pymysql.connect(
                # ใช้ข้อมูลการเชื่อมต่อเดียวกับในไฟล์ total_rental_stock.py
                host='150.95.26.61',
                user='greenhome',
                password='NPD@db789',
                database='npd_db',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )

            # คิวรีสำหรับ ใบเสร็จใบกำกับเช่า (ปรับปรุง)
            query = """
                SELECT 
                    ir.inv_no, 
                    ir.dateissue, 
                    ir.inv_rentid, 
                    mb.branch_name, 
                    c.cus_fullname, 
                    c.cus_cpnname, 
                    c.cus_cpntaxid, 
                    c.cus_cpnadd, 
                    c.cus_cpntel, 
                    ROUND(ir.inv_rentperday, 2) AS rent_perday, 
                    ir.inv_days, 
                    ir.inv_statustax, 
                    ROUND(ir.inv_rentperday * ir.inv_days, 2) AS rent_amount,
                    CONCAT(em.emp_title, ' ', em.emp_name, ' ', em.emp_surname, ' (', em.emp_nickname, ')') AS full_create
                FROM 
                    npd_db.invandreceipt_rent AS ir
                LEFT JOIN 
                    npd_db.master_branch AS mb ON ir.branchid = mb.branch_id
                LEFT JOIN 
                    npd_db.master_customer AS c ON ir.inv_cusid = c.cus_id
                LEFT JOIN 
                    npd_db.master_employee AS em ON ir.userissue = em.emp_id
                WHERE 
                    ir.dateissue >= DATE '2025-06-01'
                    AND ir.cancel = 'N'
                ORDER BY ir.dateissue DESC, ir.inv_no DESC
            """

            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            # ลบข้อมูลเก่าทั้งหมดก่อนสร้างใหม่
            self.search([]).sudo().unlink()

            for row in results:
                self.create({
                    'inv_no': row.get('inv_no'),
                    'dateissue': row.get('dateissue'),
                    'inv_rentid': row.get('inv_rentid'),
                    'branch_name': row.get('branch_name'),
                    'cus_fullname': row.get('cus_fullname'),
                    'cus_cpnname': row.get('cus_cpnname'),
                    'cus_cpntaxid': row.get('cus_cpntaxid'),
                    'cus_cpnadd': row.get('cus_cpnadd'),
                    'cus_cpntel': row.get('cus_cpntel'),
                    'rent_perday': row.get('rent_perday'),
                    'inv_days': row.get('inv_days'),
                    'inv_statustax': row.get('inv_statustax'),
                    'full_create': row.get('full_create'),  # บันทึกฟิลด์ใหม่
                    # Odoo จะคำนวณ rent_amount ให้อัตโนมัติ
                })
        except Exception as e:
            raise UserError(f"❌ ดึงข้อมูลใบเสร็จใบกำกับเช่าไม่สำเร็จ: {str(e)}")