# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql
import datetime


class QuotationSummary(models.Model):
    _name = 'baankheaw.quotation_summary'
    _description = 'ใบเสนอราคาเช่า'

    # Fields based on the provided query
    quotation_date = fields.Date(string='วันที่เอกสาร')
    branch_name = fields.Char(string='สาขา')
    fullname = fields.Char(string='ผู้บันทึก')
    nickname = fields.Char(string='ชื่อเล่นผู้บันทึก')

    def action_update_realtime_quotation_data(self):
        self.env['baankheaw.quotation_summary'].sudo().fetch_and_store_realtime_data_summary()

    @api.model
    def fetch_and_store_realtime_data_summary(self):
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

            query = f"""
            SELECT 
                qh.*,
                mb.branch_name,
                CONCAT(me.emp_name, ' ', me.emp_surname) AS fullname,
                me.emp_nickname AS nickname
            FROM npd_db.quotation_head qh
            LEFT JOIN npd_db.master_branch mb
                ON qh.branchid = mb.branch_id
            LEFT JOIN npd_db.master_employee me 
                ON qh.userissue = me.emp_id
            WHERE qh.dateissue >= '{start_of_year}'
            """

            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            # ✅ แก้ไขตรงนี้: ลบเฉพาะข้อมูลที่มีวันที่เอกสารในปีปัจจุบัน
            self.search([('quotation_date', '>=', start_of_year)]).sudo().unlink()

            for row in results:
                self.create({
                    'quotation_date': row.get('dateissue'),
                    'branch_name': row.get('branch_name'),
                    'fullname': row.get('fullname'),
                    'nickname': row.get('nickname'),
                })
        except Exception as e:
            raise UserError(f"❌ ดึงข้อมูลไม่สำเร็จ: {str(e)}")