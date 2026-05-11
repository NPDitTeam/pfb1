# -*- coding: utf-8 -*-
from odoo import models, fields, tools
import logging

_logger = logging.getLogger(__name__)


class DebtReportSummary(models.Model):
    _name = 'npd.debt.report.summary'
    _description = 'รายงานติดตามหนี้ทั้งหมด'
    _auto = False  # SQL View - ไม่สร้างตารางอัตโนมัติ
    _order = 'arh_date asc'

    row_no = fields.Integer(string='ลำดับ', readonly=True)
    cus_fullname = fields.Char(string='ลูกค้า', readonly=True)
    cus_tel = fields.Char(string='เบอร์ลูกค้า', readonly=True)
    cus_address = fields.Text(string='ที่อยู่ลูกค้า', readonly=True)
    cus_cpnname = fields.Char(string='บริษัท', readonly=True)
    cus_cpnadd = fields.Text(string='ที่อยู่บริษัท', readonly=True)
    cus_cpntel = fields.Char(string='เบอร์บริษัท', readonly=True)
    branch_name = fields.Char(string='สาขา', readonly=True)
    amount = fields.Float(string='ค่าเช่า', readonly=True)
    vat = fields.Float(string='VAT 7%', readonly=True)
    tax = fields.Float(string='หัก ณ ที่จ่าย', readonly=True)
    insure = fields.Float(string='ค่าประกัน', readonly=True)
    lost = fields.Float(string='ค่าปรับหาย', readonly=True)
    broken = fields.Float(string='ค่าปรับชำรุด', readonly=True)
    transport = fields.Float(string='ค่าขนส่ง', readonly=True)
    total_debt = fields.Float(string='หนี้รวม', readonly=True)
    total_paid = fields.Float(string='รับชำระ', readonly=True)
    remaining_balance = fields.Float(string='คงเหลือ', readonly=True)
    bill_status = fields.Char(string='สถานะบิล', readonly=True)
    customer_id = fields.Char(string='รหัสลูกค้า', readonly=True)
    arh_date = fields.Date(string='วันที่เริ่มเป็นหนี้', readonly=True)
    due_date = fields.Date(string='วันครบกำหนดชำระ', readonly=True)
    debt_duration = fields.Integer(string='จำนวนวันที่นับตั้งแต่เริ่มหนี้', readonly=True)
    responsible_party = fields.Char(string='ส่วนรับผิดชอบ', readonly=True)

    def init(self):
        """Create SQL View for debt report summary"""
        cr = self._cr
        
        # Drop view ถ้ามีอยู่
        tools.drop_view_if_exists(cr, self._table)
        
        # ตรวจสอบว่า baankheaw_debtor_summary มีอยู่หรือไม่
        cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'baankheaw_debtor_summary'
            )
        """)
        table_exists = cr.fetchone()[0]
        
        if table_exists:
            # สร้าง View จริงที่ดึงข้อมูลจาก baankheaw_debtor_summary
            _logger.info("Creating npd_debt_report_summary view with data from baankheaw_debtor_summary")
            cr.execute("""
                CREATE OR REPLACE VIEW %s AS (
                    SELECT 
                        ROW_NUMBER() OVER(ORDER BY cus_fullname) AS id,
                        ROW_NUMBER() OVER(ORDER BY cus_fullname) AS row_no,
                        cus_fullname,
                        cus_tel,
                        cus_address,
                        cus_cpnname,
                        cus_cpnadd,
                        cus_cpntel,
                        branch_name,
                        amount,
                        vat,
                        tax,
                        insure,
                        lost,
                        broken,
                        transport,
                        total_debt,
                        total_paid,
                        remaining_balance,
                        bill_status,
                        customer_id,
                        arh_date,
                        due_date,
                        debt_duration,
                        responsible_party
                    FROM baankheaw_debtor_summary
                    WHERE branch_name <> 'สำนักงานใหญ่'
                )
            """ % (self._table,))
        else:
            # สร้าง Empty View สำหรับ database ที่ไม่มีตาราง baankheaw_debtor_summary
            _logger.info("Creating empty npd_debt_report_summary view (baankheaw_debtor_summary not found)")
            cr.execute("""
                CREATE OR REPLACE VIEW %s AS (
                    SELECT 
                        1::bigint AS id,
                        0::integer AS row_no,
                        NULL::varchar AS cus_fullname,
                        NULL::varchar AS cus_tel,
                        NULL::text AS cus_address,
                        NULL::varchar AS cus_cpnname,
                        NULL::text AS cus_cpnadd,
                        NULL::varchar AS cus_cpntel,
                        NULL::varchar AS branch_name,
                        0::numeric AS amount,
                        0::numeric AS vat,
                        0::numeric AS tax,
                        0::numeric AS insure,
                        0::numeric AS lost,
                        0::numeric AS broken,
                        0::numeric AS transport,
                        0::numeric AS total_debt,
                        0::numeric AS total_paid,
                        0::numeric AS remaining_balance,
                        NULL::varchar AS bill_status,
                        NULL::varchar AS customer_id,
                        NULL::date AS arh_date,
                        NULL::date AS due_date,
                        0::integer AS debt_duration,
                        NULL::varchar AS responsible_party
                    WHERE FALSE
                )
            """ % (self._table,))
