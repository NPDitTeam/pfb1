# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pymysql
import logging

_logger = logging.getLogger(__name__)


class OldCustomerSummary(models.Model):
    _name = 'baankheaw.old_customer_summary'
    _description = 'ลูกค้าเก่า'
    _order = 'cus_id'

    # Fields ตามคิวรี
    cus_id = fields.Char(string='รหัสลูกค้า')
    cus_fullname = fields.Char(string='ชื่อลูกค้า')
    cus_address = fields.Char(string='ที่อยู่')
    cus_province = fields.Char(string='จังหวัด')
    cus_cpnname = fields.Char(string='ชื่อบริษัทลูกค้า')
    cus_cpntel = fields.Char(string='เบอร์โทรศัพท์บริษัท')
    cus_adv = fields.Char(string='ช่องทางลูกค้าเข้ามา')
    branch_name = fields.Char(string='สาขา')

    total_rent = fields.Float(string='ยอดเปิดบิลสะสม', digits=(16, 2))
    latest_issue_date = fields.Date(string='วันล่าสุดที่เปิดบิล')

    def action_update_old_customer_data(self):
        """ปุ่มอัปเดตข้อมูลจาก DB ภายนอก"""
        self.env['baankheaw.old_customer_summary'].sudo().fetch_and_store_old_customer_data()

    @api.model
    def fetch_and_store_old_customer_data(self):
        """ดึงข้อมูลตามคิวรีที่กำหนดและบันทึกเข้า model นี้"""
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
                    c.cus_id, 
                    c.cus_fullname, 
                    c.cus_address, 
                    c.cus_province, 
                    c.cus_cpnname, 
                    c.cus_cpntel, 
                    c.cus_adv, 
                    b.branch_name,
                    r.total_rent AS total_rent,
                    r.latest_issue_date AS latest_issue_date
                FROM 
                    npd_db.master_customer AS c
                LEFT JOIN 
                    npd_db.master_branch AS b ON b.branch_id = c.branchid
                INNER JOIN (
                    SELECT 
                        renth_cusid,
                        SUM(renth_rentactual_return) AS total_rent,
                        MAX(dateissue) AS latest_issue_date
                    FROM 
                        npd_db.rentorder_head
                    WHERE 
                        renth_return = 'Y' 
                        AND renth_cancel = 'N'
                    GROUP BY 
                        renth_cusid
                    HAVING SUM(renth_rentactual_return) > 15000
                ) AS r ON r.renth_cusid = c.cus_id
                WHERE 
                    c.cus_blacklist = 'N' 
                    AND c.cus_warning = 'N' 
                    AND c.cus_active = 'Y'
                    AND b.branch_id NOT IN ('01', '10', '14', '23', '99', '24', '98', '88')
                    AND c.cus_id != '06-C000001';
            """

            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            # ล้างข้อมูลเก่า แล้วสร้างใหม่
            self.search([]).sudo().unlink()

            for r in rows:
                self.create({
                    'cus_id': r.get('cus_id'),
                    'cus_fullname': r.get('cus_fullname'),
                    'cus_address': r.get('cus_address'),
                    'cus_province': r.get('cus_province'),
                    'cus_cpnname': r.get('cus_cpnname'),
                    'cus_cpntel': r.get('cus_cpntel'),
                    'cus_adv': r.get('cus_adv'),
                    'branch_name': r.get('branch_name'),
                    'total_rent': r.get('total_rent') or 0.0,
                    'latest_issue_date': r.get('latest_issue_date'),
                })
        except Exception as e:
            raise UserError(f"❌ ดึงข้อมูลลูกค้าเก่าไม่สำเร็จ: {str(e)}")
