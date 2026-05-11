# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

try:
    import pymysql
except ImportError:
    pymysql = None
    _logger.warning('pymysql not installed. Please install it with: pip install pymysql')


class NpdDebtTrackingBaankhiewInvoice(models.Model):
    _name = 'npd.debt.tracking.baankhiew.invoice'
    _description = 'ใบแจ้งหนี้จากบ้านเขียว'
    _order = 'branch_name, cus_fullname, invoice_number'
    _rec_name = 'invoice_number'

    customer_id = fields.Char(string='ID ลูกค้า')
    cus_fullname = fields.Char(string='ชื่อลูกค้า')
    cus_tel = fields.Char(string='เบอร์ลูกค้า')
    cus_address = fields.Char(string='ที่อยู่ลูกค้า')
    cus_cpnname = fields.Char(string='ชื่อบริษัท')
    cus_cpntel = fields.Char(string='เบอร์บริษัท')
    cus_cpnadd = fields.Char(string='ที่อยู่บริษัท')
    cus_cpntaxid = fields.Char(string='เลขประจำตัวผู้เสียภาษี')
    cus_cpnprovince = fields.Char(string='จังหวัดบริษัท')
    cus_cpnzipcode = fields.Char(string='รหัสไปรษณีย์บริษัท')

    branch_name = fields.Char(string='สาขา')
    invoice_number = fields.Char(string='เลขที่ใบกำกับเช่า')
    arh_num = fields.Char(string='เลขที่ AR (Unique)')

    amount = fields.Float(string='ค่าเช่า')
    vat = fields.Float(string='Vat')
    tax = fields.Float(string='Tax')
    insure = fields.Float(string='ค่าประกัน')
    lost = fields.Float(string='ค่าปรับหาย')
    transport = fields.Float(string='ค่าขนส่ง')

    total_debt = fields.Float(string='หนี้รวม')
    total_paid = fields.Float(string='ยอดรับชำระ')
    remaining_balance = fields.Float(string='ค้างชำระสุทธิ')

    arh_date = fields.Date(string='วันที่เริ่มหนี้')
    due_date = fields.Date(string='วันที่ครบกำหนดชำระ')
    debt_duration = fields.Integer(string='ระยะเวลาที่เป็นหนี้ (วัน)')
    responsible_party = fields.Char(string='ผู้รับผิดชอบ')
    bill_status = fields.Char(string='สถานะบิล')

    def name_get(self):
        """แสดงเฉพาะเลขเอกสารเท่านั้น"""
        result = []
        for rec in self:
            name = rec.invoice_number or 'N/A'
            result.append((rec.id, name))
        return result

    @api.model
    def _get_mysql_connection(self):
        """สร้าง connection ไปยัง MySQL บ้านเขียว"""
        if not pymysql:
            raise UserError(_('กรุณาติดตั้ง pymysql: pip install pymysql'))

        return pymysql.connect(
            host='150.95.26.61',
            user='greenhome',
            password='NPD@db789',
            database='npd_db',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

    @api.model
    def _get_baankhiew_query(self):
        """Query สำหรับดึงข้อมูลใบแจ้งหนี้จากบ้านเขียว (ไม่เช็ค amount > 0 แล้ว)"""
        return """
        SELECT
            h.arh_cusid AS customer_id,
            h.num AS arh_num,
            c.cus_fullname AS cus_fullname,
            c.cus_tel AS cus_tel,
            c.cus_address AS cus_address,
            c.cus_cpnname AS cus_cpnname,
            c.cus_cpntel AS cus_cpntel,
            c.cus_cpnadd AS cus_cpnadd,
            c.cus_cpntaxid AS cus_cpntaxid,
            c.cus_cpnprovince AS cus_cpnprovince,
            c.cus_cpnzipcode AS cus_cpnzipcode,
            b.branch_name AS branch_name,
            h.arh_docid AS invoice_number,
            COALESCE(h.arh_amount, 0) AS amount,
            COALESCE(h.arh_vat, 0) AS vat,
            COALESCE(h.arh_tax, 0) AS tax,
            COALESCE(h.arh_insure, 0) AS insure,
            COALESCE(h.arh_lost, 0) AS lost,
            COALESCE(h.arh_transport, 0) AS transport,
            (
                COALESCE(h.arh_amount,0) +
                COALESCE(h.arh_vat,0)
            ) AS total_debt,
            COALESCE(repay_sum.total_repay, 0) AS total_paid,
            (
                COALESCE(h.arh_amount,0) +
                COALESCE(h.arh_vat,0)
            ) - COALESCE(repay_sum.total_repay, 0) AS remaining_balance,
            rh.renth_datestart AS arh_date,
            rh.renth_dateend AS due_date,
            DATEDIFF(CURDATE(), rh.renth_datestart) AS debt_duration,
            CASE
                WHEN DATEDIFF(CURDATE(), rh.renth_datestart) BETWEEN 0 AND 45 THEN 'สาขา & sales'
                WHEN DATEDIFF(CURDATE(), rh.renth_datestart) BETWEEN 46 AND 90 THEN 'ส่วนกลาง'
                WHEN DATEDIFF(CURDATE(), rh.renth_datestart) > 90
                    AND ((
                        COALESCE(h.arh_amount,0) +
                        COALESCE(h.arh_vat,0)
                    ) - COALESCE(repay_sum.total_repay, 0)) >= 500000 THEN 'นิติกร'
                WHEN DATEDIFF(CURDATE(), rh.renth_datestart) > 90
                    AND ((
                        COALESCE(h.arh_amount,0) +
                        COALESCE(h.arh_vat,0)
                    ) - COALESCE(repay_sum.total_repay, 0)) < 500000 THEN 'ส่วนกลาง'
                ELSE 'ไม่ระบุ'
            END AS responsible_party,
            CASE 
                WHEN rh.renth_return = 'Y' THEN 'ปิดบิล'
                WHEN rh.renth_return = 'N' THEN 'ยังไม่ปิดบิล'
                ELSE 'ไม่มีข้อมูล'
            END AS bill_status_display
        FROM npd_db.ar_head h
        JOIN npd_db.master_customer c
            ON TRIM(h.arh_cusid) = TRIM(c.cus_id)
        JOIN npd_db.master_branch b
            ON TRIM(h.branchid) = TRIM(b.branch_id)
        LEFT JOIN npd_db.rentorder_head rh
            ON rh.renth_id = h.arh_docid
            AND rh.renth_cancel = 'N'
        LEFT JOIN (
            SELECT 
                arh_num,
                SUM(
                    COALESCE(arp_amount,0) +
                    COALESCE(arp_vat,0) +
                    COALESCE(arp_tax,0) +
                    COALESCE(arp_insure,0) +
                    COALESCE(arp_lost,0) +
                    COALESCE(arp_broken,0) +
                    COALESCE(arp_transport,0)
                ) AS total_repay
            FROM npd_db.ar_repay
            WHERE cancel = 'N'
            GROUP BY arh_num
        ) repay_sum
            ON repay_sum.arh_num = h.num
        WHERE h.cancel = 'N'
            AND (
                COALESCE(h.arh_amount,0) +
                COALESCE(h.arh_vat,0)
            ) - COALESCE(repay_sum.total_repay, 0) > 0
            AND h.arh_amount > 0
            AND c.cus_cpntaxid = %s
        ORDER BY b.branch_name, c.cus_fullname, h.arh_docid
        """

    @api.model
    def fetch_invoices_by_customer(self, partner_vat):
        """ดึงข้อมูลใบแจ้งหนี้จากฐานข้อมูลบ้านเขียวตามเลขประจำตัวผู้เสียภาษี
        Returns: list of invoice record IDs
        """
        if not partner_vat:
            _logger.warning('fetch_invoices_by_customer: No partner_vat provided')
            return []

        created_ids = []
        _logger.info('========== BAANKHIEW FETCH START ==========')
        _logger.info('Partner VAT from Odoo: [%s]', partner_vat)

        try:
            conn = self._get_mysql_connection()
            cursor = conn.cursor()

            # ค้นหาด้วยเลขประจำตัวผู้เสียภาษี
            search_vat = partner_vat.strip()
            _logger.info('Searching by cus_cpntaxid: [%s]', search_vat)

            query = self._get_baankhiew_query()
            cursor.execute(query, (search_vat,))
            results = cursor.fetchall()

            conn.close()

            _logger.info('Total results found: %d', len(results))
            if results:
                for i, r in enumerate(results[:3]):
                    _logger.info('Result %d: cus_fullname=[%s], invoice_number=[%s], arh_num=[%s], cus_cpntaxid=[%s]',
                               i+1, r.get('cus_fullname'), r.get('invoice_number'), r.get('arh_num'), r.get('cus_cpntaxid'))

            # ลบข้อมูลเก่าของลูกค้าก่อนดึงใหม่ (ใช้ cus_cpntaxid)
            if results:
                tax_ids = list(set([r.get('cus_cpntaxid') for r in results if r.get('cus_cpntaxid')]))
                if tax_ids:
                    old_records = self.search([('cus_cpntaxid', 'in', tax_ids)])
                    if old_records:
                        _logger.info('Deleting %d old records for tax IDs: %s', len(old_records), tax_ids)
                        old_records.sudo().unlink()

            # สร้างข้อมูลใหม่
            for row in results:
                vals = {
                    'customer_id': row.get('customer_id'),
                    'arh_num': row.get('arh_num'),
                    'cus_fullname': row.get('cus_fullname'),
                    'cus_tel': row.get('cus_tel'),
                    'cus_address': row.get('cus_address'),
                    'cus_cpnname': row.get('cus_cpnname'),
                    'cus_cpntel': row.get('cus_cpntel'),
                    'cus_cpnadd': row.get('cus_cpnadd'),
                    'cus_cpntaxid': row.get('cus_cpntaxid'),
                    'cus_cpnprovince': row.get('cus_cpnprovince'),
                    'cus_cpnzipcode': row.get('cus_cpnzipcode'),
                    'branch_name': row.get('branch_name'),
                    'invoice_number': row.get('invoice_number'),
                    'amount': row.get('amount', 0),
                    'vat': row.get('vat', 0),
                    'tax': row.get('tax', 0),
                    'insure': row.get('insure', 0),
                    'lost': row.get('lost', 0),
                    'transport': row.get('transport', 0),
                    'total_debt': row.get('total_debt', 0),
                    'total_paid': row.get('total_paid', 0),
                    'remaining_balance': row.get('remaining_balance', 0),
                    'arh_date': row.get('arh_date'),
                    'due_date': row.get('due_date'),
                    'debt_duration': row.get('debt_duration', 0),
                    'responsible_party': row.get('responsible_party'),
                    'bill_status': row.get('bill_status_display'),
                }
                new_rec = self.sudo().create(vals)
                created_ids.append(new_rec.id)

            _logger.info('Created/Updated %d invoices for partner_vat: %s', len(created_ids), partner_vat)
            _logger.info('Returning invoice IDs: %s', created_ids)
            _logger.info('========== BAANKHIEW FETCH END ==========')

        except Exception as e:
            _logger.error('========== BAANKHIEW FETCH ERROR ==========')
            _logger.error('Error fetching invoices from Baankhiew: %s', str(e))
            _logger.exception(e)

        return created_ids

    @api.model
    def action_test_connection(self):
        """ทดสอบ connection กับ MySQL บ้านเขียว (ค่าเช่า)"""
        try:
            conn = self._get_mysql_connection()
            cursor = conn.cursor()

            test_query = """
            SELECT DISTINCT c.cus_fullname, COUNT(*) as invoice_count
            FROM npd_db.ar_head h
            JOIN npd_db.master_customer c ON TRIM(h.arh_cusid) = TRIM(c.cus_id)
            WHERE h.cancel = 'N'
            GROUP BY c.cus_fullname
            ORDER BY invoice_count DESC
            LIMIT 10
            """
            cursor.execute(test_query)
            results = cursor.fetchall()
            conn.close()

            if results:
                customer_list = '\n'.join(['- %s (%d ใบ)' % (r['cus_fullname'], r['invoice_count']) for r in results])
                message = 'เชื่อมต่อสำเร็จ!\n\nตัวอย่างลูกค้าที่มีใบแจ้งหนี้มากที่สุด:\n%s' % customer_list
            else:
                message = 'เชื่อมต่อสำเร็จ แต่ไม่พบข้อมูลในฐานข้อมูล'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('ผลการทดสอบ'),
                    'message': message,
                    'type': 'success',
                    'sticky': True,
                }
            }

        except Exception as e:
            _logger.error('Test connection error: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('เชื่อมต่อไม่สำเร็จ'),
                    'message': _('Error: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }


class NpdDebtTrackingBaankhiewDamageInvoice(models.Model):
    """Model สำหรับเก็บข้อมูลค่าปรับชำรุดจากบ้านเขียว"""
    _name = 'npd.debt.tracking.baankhiew.damage.invoice'
    _description = 'ใบแจ้งหนี้ค่าปรับชำรุดจากบ้านเขียว'
    _order = 'branch_name, inv_cusname, inv_no'
    _rec_name = 'inv_no'

    inv_no = fields.Char(string='เลขเอกสาร')
    inv_cusname = fields.Char(string='ชื่อลูกค้า')
    cus_cpnname = fields.Char(string='บริษัท')
    cus_cpntaxid = fields.Char(string='เลขประจำตัวผู้เสียภาษี')
    cus_cpnadd = fields.Char(string='ที่อยู่บริษัท')
    cus_cpnprovince = fields.Char(string='จังหวัดบริษัท')
    cus_cpnzipcode = fields.Char(string='รหัสไปรษณีย์บริษัท')
    cus_cpntel = fields.Char(string='เบอร์บริษัท')
    branch_name = fields.Char(string='สาขา')
    inv_amount = fields.Float(string='ค่าปรับชำรุด')
    total_paid = fields.Float(string='รับชำระ')
    remaining_balance = fields.Float(string='คงเหลือ')
    dateissue = fields.Date(string='วันที่')
    
    # Keep old fields for backward compatibility
    inv_docid = fields.Char(string='เลขเอกสารเช่า')
    inv_cusaddress = fields.Char(string='ที่อยู่')
    inv_cusprovince = fields.Char(string='จังหวัด')
    inv_custel = fields.Char(string='เบอร์ติดต่อ')
    inv_custaxid = fields.Char(string='เลขภาษี')

    def name_get(self):
        """แสดงเฉพาะเลขเอกสารเท่านั้น"""
        result = []
        for rec in self:
            name = rec.inv_no or 'N/A'
            result.append((rec.id, name))
        return result

    @api.model
    def _get_damage_query(self):
        """Query สำหรับดึงข้อมูลค่าปรับชำรุดจากบ้านเขียว"""
        return """
        SELECT
            h.arh_date AS วันที่,
            h.arh_docid AS เลขเอกสาร,
            c.cus_fullname AS ลูกค้า,
            c.cus_cpnname AS บริษัท,
            c.cus_cpntaxid AS เลขภาษี,
            c.cus_cpnadd AS ที่อยู่บริษัท,
            c.cus_cpnprovince AS จังหวัดบริษัท,
            c.cus_cpnzipcode AS รหัสไปรษณีย์บริษัท,
            c.cus_cpntel AS เบอร์บริษัท,
            b.branch_name AS สาขา,
            COALESCE(h.arh_broken, 0) AS ค่าปรับชำรุด,
            COALESCE(SUM(r.arp_broken), 0) AS รับชำระ,
            COALESCE(h.arh_broken, 0) - COALESCE(SUM(r.arp_broken), 0) AS คงเหลือ
        FROM npd_db.ar_head h
        JOIN npd_db.master_customer c
            ON TRIM(h.arh_cusid) = TRIM(c.cus_id)
        JOIN npd_db.master_branch b
            ON TRIM(h.branchid) = TRIM(b.branch_id)
        LEFT JOIN npd_db.ar_repay r
            ON r.arp_docid = h.arh_docid
        WHERE h.cancel = 'N' 
            AND h.arh_broken != 0
            AND c.cus_cpntaxid = %s
        GROUP BY 
            h.arh_date,
            h.arh_docid, 
            c.cus_fullname, 
            c.cus_cpnname,
            c.cus_cpntaxid,
            c.cus_cpnadd,
            c.cus_cpnprovince,
            c.cus_cpnzipcode,
            c.cus_cpntel,
            b.branch_name, 
            h.arh_broken
        HAVING COALESCE(h.arh_broken, 0) - COALESCE(SUM(r.arp_broken), 0) > 0
        ORDER BY h.arh_date DESC
        """

    @api.model
    def fetch_damage_invoices_by_customer(self, partner_vat):
        """ดึงข้อมูลค่าปรับชำรุดจากฐานข้อมูลบ้านเขียวตามเลขประจำตัวผู้เสียภาษี
        Returns: list of damage invoice record IDs
        """
        if not partner_vat:
            _logger.warning('fetch_damage_invoices_by_customer: No partner_vat provided')
            return []

        created_ids = []
        _logger.info('========== BAANKHIEW DAMAGE FETCH START ==========')
        _logger.info('Partner VAT from Odoo: [%s]', partner_vat)

        try:
            # ใช้ connection เดียวกับ invoice model
            InvoiceModel = self.env['npd.debt.tracking.baankhiew.invoice']
            conn = InvoiceModel._get_mysql_connection()
            cursor = conn.cursor()

            # ค้นหาด้วยเลขประจำตัวผู้เสียภาษี
            search_vat = partner_vat.strip()
            _logger.info('Searching damage by cus_cpntaxid: [%s]', search_vat)

            query = self._get_damage_query()
            cursor.execute(query, (search_vat,))
            results = cursor.fetchall()

            conn.close()

            _logger.info('Total damage results found: %d', len(results))
            if results:
                for i, r in enumerate(results[:3]):
                    _logger.info('Damage Result %d: บริษัท=[%s], เลขเอกสาร=[%s], คงเหลือ=[%s], เลขภาษี=[%s]',
                               i+1, r.get('บริษัท'), r.get('เลขเอกสาร'), r.get('คงเหลือ'), r.get('เลขภาษี'))

            # ลบข้อมูลเก่าของบริษัทก่อนดึงใหม่ (ใช้ cus_cpntaxid)
            if results:
                tax_ids = list(set([r.get('เลขภาษี') for r in results if r.get('เลขภาษี')]))
                if tax_ids:
                    old_records = self.search([('cus_cpntaxid', 'in', tax_ids)])
                    if old_records:
                        _logger.info('Deleting %d old damage records for tax IDs: %s', len(old_records), tax_ids)
                        old_records.sudo().unlink()

            # สร้างข้อมูลใหม่
            for row in results:
                remaining = row.get('คงเหลือ', 0) or 0
                # ข้ามถ้ายอดคงเหลือเป็น 0 หรือติดลบ
                if remaining <= 0:
                    _logger.info('Skipping เลขเอกสาร=[%s] because คงเหลือ=[%s] <= 0', 
                               row.get('เลขเอกสาร'), remaining)
                    continue
                    
                vals = {
                    'inv_no': row.get('เลขเอกสาร'),
                    'inv_cusname': row.get('ลูกค้า'),
                    'cus_cpnname': row.get('บริษัท'),
                    'cus_cpntaxid': row.get('เลขภาษี'),
                    'cus_cpnadd': row.get('ที่อยู่บริษัท'),
                    'cus_cpnprovince': row.get('จังหวัดบริษัท'),
                    'cus_cpnzipcode': row.get('รหัสไปรษณีย์บริษัท'),
                    'cus_cpntel': row.get('เบอร์บริษัท'),
                    'branch_name': row.get('สาขา'),
                    'inv_amount': row.get('ค่าปรับชำรุด', 0),
                    'total_paid': row.get('รับชำระ', 0),
                    'remaining_balance': remaining,
                    'dateissue': row.get('วันที่'),
                }
                new_rec = self.sudo().create(vals)
                created_ids.append(new_rec.id)

            _logger.info('Created/Updated %d damage invoices for partner_vat: %s', len(created_ids), partner_vat)
            _logger.info('========== BAANKHIEW DAMAGE FETCH END ==========')

        except Exception as e:
            _logger.error('========== BAANKHIEW DAMAGE FETCH ERROR ==========')
            _logger.error('Error fetching damage invoices from Baankhiew: %s', str(e))
            _logger.exception(e)

        return created_ids



class NpdDebtTrackingBaankhiewLostInvoice(models.Model):
    """Model สำหรับเก็บข้อมูลค่าปรับหายจากบ้านเขียว"""
    _name = 'npd.debt.tracking.baankhiew.lost.invoice'
    _description = 'ใบแจ้งหนี้ค่าปรับหายจากบ้านเขียว'
    _order = 'branch_name, cus_fullname, doc_id'
    _rec_name = 'doc_id'

    # ข้อมูลจาก ar_head
    doc_id = fields.Char(string='เลขเอกสาร')
    arh_date = fields.Date(string='วันที่')
    cus_fullname = fields.Char(string='ชื่อลูกค้า')
    cus_cpnname = fields.Char(string='บริษัท')
    cus_cpntaxid = fields.Char(string='เลขประจำตัวผู้เสียภาษี')
    cus_cpnadd = fields.Char(string='ที่อยู่บริษัท')
    cus_cpnprovince = fields.Char(string='จังหวัดบริษัท')
    cus_cpnzipcode = fields.Char(string='รหัสไปรษณีย์บริษัท')
    cus_cpntel = fields.Char(string='เบอร์บริษัท')
    branch_name = fields.Char(string='สาขา')
    
    # ข้อมูลจากบิลคืน
    sale_name = fields.Char(string='ชื่อเซลล์')
    date_start = fields.Date(string='เริ่มเช่า')
    date_return = fields.Date(string='วันคืน')
    
    # ข้อมูลค่าปรับหายจากบิลคืน
    amt_lost_return = fields.Float(string='ค่าปรับหาย')
    discount_lost_return = fields.Float(string='ส่วนลดค่าปรับหาย')
    net_lost = fields.Float(string='ปรับหายสุทธิ')
    vat_7_percent = fields.Float(string='ภาษีมูลค่าเพิ่ม 7%')
    before_vat = fields.Float(string='ค่าสินค้าก่อนภาษี')
    
    # ข้อมูลค่าปรับและรับชำระจาก AR
    arh_lost = fields.Float(string='ค่าปรับชำรุด(AR)')
    total_paid = fields.Float(string='รับชำระ')
    remaining_balance = fields.Float(string='คงเหลือ')
    
    # รายการสินค้าที่ปรับหาย
    detail_ids = fields.One2many('npd.debt.tracking.baankhiew.lost.detail', 'lost_invoice_id',
        string='รายการสินค้าปรับหาย')

    def name_get(self):
        """แสดงเฉพาะเลขเอกสารเท่านั้น"""
        result = []
        for rec in self:
            name = rec.doc_id or 'N/A'
            result.append((rec.id, name))
        return result

    @api.model
    def _get_lost_query(self):
        """Query สำหรับดึงข้อมูลค่าปรับหายจากบ้านเขียว"""
        return """
        SELECT
            h.arh_date AS วันที่,
            h.arh_docid AS เลขเอกสาร,
            c.cus_fullname AS ลูกค้า,
            c.cus_cpnname AS บริษัท,
            c.cus_cpntaxid AS เลขภาษี,
            c.cus_cpnadd AS ที่อยู่บริษัท,
            c.cus_cpnprovince AS จังหวัดบริษัท,
            c.cus_cpnzipcode AS รหัสไปรษณีย์บริษัท,
            c.cus_cpntel AS เบอร์บริษัท,
            b.branch_name AS สาขา,
            rh.renth_salename AS ชื่อเซลล์,
            rh.renth_datestart AS เริ่มเช่า,
            rh.renth_date_return AS วันคืน,
            COALESCE(rh.renth_amtlost_return, 0) AS ค่าปรับหาย,
            COALESCE(rh.renth_discountlost_return, 0) AS ส่วนลดค่าปรับหาย,
            COALESCE(rh.renth_amtlost_return, 0) - COALESCE(rh.renth_discountlost_return, 0) AS ปรับหายสุทธิ,
            ROUND((COALESCE(rh.renth_amtlost_return, 0) - COALESCE(rh.renth_discountlost_return, 0)) * 7 / 107, 2) AS ภาษีมูลค่าเพิ่ม,
            ROUND((COALESCE(rh.renth_amtlost_return, 0) - COALESCE(rh.renth_discountlost_return, 0)) * 100 / 107, 2) AS ก่อนภาษี,
            COALESCE(h.arh_lost, 0) AS ค่าปรับชำรุด,
            COALESCE(SUM(r.arp_lost), 0) AS รับชำระ,
            COALESCE(h.arh_lost, 0) - COALESCE(SUM(r.arp_lost), 0) AS คงเหลือ
        FROM npd_db.ar_head h
        JOIN npd_db.master_customer c
            ON TRIM(h.arh_cusid) = TRIM(c.cus_id)
        JOIN npd_db.master_branch b
            ON TRIM(h.branchid) = TRIM(b.branch_id)
        LEFT JOIN npd_db.ar_repay r
            ON r.arp_docid = h.arh_docid
        LEFT JOIN npd_db.rentorder_head rh
            ON h.arh_docid = rh.renth_id
            AND rh.renth_cancel = 'N'
            AND rh.renth_bookingcancel = 'N'
            AND rh.renth_return = 'Y'
        WHERE h.cancel = 'N' 
            AND h.arh_lost != 0
            AND c.cus_cpntaxid = %s
        GROUP BY 
            h.arh_date,
            h.arh_docid, 
            c.cus_fullname, 
            c.cus_cpnname, 
            c.cus_cpntaxid,
            c.cus_cpnadd,
            c.cus_cpnprovince,
            c.cus_cpnzipcode,
            c.cus_cpntel,
            b.branch_name, 
            h.arh_lost,
            rh.renth_salename,
            rh.renth_datestart,
            rh.renth_date_return,
            rh.renth_amtlost_return,
            rh.renth_discountlost_return
        HAVING COALESCE(h.arh_lost, 0) - COALESCE(SUM(r.arp_lost), 0) > 0
        ORDER BY h.arh_date DESC
        """

    @api.model
    def _get_lost_detail_query(self):
        """Query สำหรับดึงรายการสินค้าที่ปรับหาย"""
        return """
        SELECT 
            d.rentd_id,
            d.rentd_proid,
            d.rentd_proname,
            d.rentd_weight,
            d.rentd_amtlost_return AS ปรับหายแต่ละชิ้น,
            (d.rentd_amount - d.rentd_amt_return) AS จำนวนสินค้าปรับหาย,
            CASE 
                WHEN (d.rentd_amount - d.rentd_amt_return) > 0 
                THEN d.rentd_amtlost_return / (d.rentd_amount - d.rentd_amt_return) 
                ELSE 0 
            END AS ราคาสินค้าต่อชิ้น
        FROM npd_db.rentorder_detail d
        WHERE d.rentd_amtlost_return != 0
            AND d.rentd_id = %s
        """

    @api.model
    def fetch_lost_invoices_by_customer(self, partner_vat):
        """ดึงข้อมูลค่าปรับหายจากฐานข้อมูลบ้านเขียวตามเลขประจำตัวผู้เสียภาษี
        Returns: list of lost invoice record IDs
        """
        if not partner_vat:
            _logger.warning('fetch_lost_invoices_by_customer: No partner_vat provided')
            return []

        created_ids = []
        _logger.info('========== BAANKHIEW LOST FETCH START ==========')
        _logger.info('Partner VAT from Odoo: [%s]', partner_vat)

        try:
            # ใช้ connection เดียวกับ invoice model
            InvoiceModel = self.env['npd.debt.tracking.baankhiew.invoice']
            conn = InvoiceModel._get_mysql_connection()
            cursor = conn.cursor()

            # ค้นหาด้วยเลขประจำตัวผู้เสียภาษี
            search_vat = partner_vat.strip()
            _logger.info('Searching lost by cus_cpntaxid: [%s]', search_vat)

            query = self._get_lost_query()
            detail_query = self._get_lost_detail_query()
            
            cursor.execute(query, (search_vat,))
            results = cursor.fetchall()

            _logger.info('Total lost results found: %d', len(results))
            if results:
                for i, r in enumerate(results[:3]):
                    _logger.info('Lost Result %d: ลูกค้า=[%s], เลขเอกสาร=[%s], คงเหลือ=[%s], เลขภาษี=[%s]',
                               i+1, r.get('ลูกค้า'), r.get('เลขเอกสาร'), r.get('คงเหลือ'), r.get('เลขภาษี'))

            # ลบข้อมูลเก่าของลูกค้าก่อนดึงใหม่ (ใช้ cus_cpntaxid)
            if results:
                tax_ids = list(set([r.get('เลขภาษี') for r in results if r.get('เลขภาษี')]))
                if tax_ids:
                    old_records = self.search([('cus_cpntaxid', 'in', tax_ids)])
                    if old_records:
                        _logger.info('Deleting %d old lost records for tax IDs: %s', len(old_records), tax_ids)
                        old_records.sudo().unlink()

            # สร้างข้อมูลใหม่
            DetailModel = self.env['npd.debt.tracking.baankhiew.lost.detail']
            
            for row in results:
                remaining = row.get('คงเหลือ', 0) or 0
                # ข้ามถ้ายอดคงเหลือเป็น 0 หรือติดลบ
                if remaining <= 0:
                    _logger.info('Skipping เลขเอกสาร=[%s] because คงเหลือ=[%s] <= 0', 
                               row.get('เลขเอกสาร'), remaining)
                    continue
                    
                vals = {
                    'doc_id': row.get('เลขเอกสาร'),
                    'arh_date': row.get('วันที่'),
                    'cus_fullname': row.get('ลูกค้า'),
                    'cus_cpnname': row.get('บริษัท'),
                    'cus_cpntaxid': row.get('เลขภาษี'),
                    'cus_cpnadd': row.get('ที่อยู่บริษัท'),
                    'cus_cpnprovince': row.get('จังหวัดบริษัท'),
                    'cus_cpnzipcode': row.get('รหัสไปรษณีย์บริษัท'),
                    'cus_cpntel': row.get('เบอร์บริษัท'),
                    'branch_name': row.get('สาขา'),
                    'sale_name': row.get('ชื่อเซลล์'),
                    'date_start': row.get('เริ่มเช่า'),
                    'date_return': row.get('วันคืน'),
                    'amt_lost_return': row.get('ค่าปรับหาย', 0),
                    'discount_lost_return': row.get('ส่วนลดค่าปรับหาย', 0),
                    'net_lost': row.get('ปรับหายสุทธิ', 0),
                    'vat_7_percent': row.get('ภาษีมูลค่าเพิ่ม', 0),
                    'before_vat': row.get('ก่อนภาษี', 0),
                    'arh_lost': row.get('ค่าปรับชำรุด', 0),
                    'total_paid': row.get('รับชำระ', 0),
                    'remaining_balance': remaining,
                }
                new_rec = self.sudo().create(vals)
                created_ids.append(new_rec.id)
                
                # ดึงรายการสินค้าที่ปรับหาย
                doc_id = row.get('เลขเอกสาร')
                if doc_id:
                    cursor.execute(detail_query, (doc_id,))
                    detail_results = cursor.fetchall()
                    _logger.info('Found %d detail items for doc_id=[%s]', len(detail_results), doc_id)
                    
                    for detail_row in detail_results:
                        detail_vals = {
                            'lost_invoice_id': new_rec.id,
                            'rentd_id': detail_row.get('rentd_id'),
                            'product_id': detail_row.get('rentd_proid'),
                            'product_name': detail_row.get('rentd_proname'),
                            'weight': detail_row.get('rentd_weight', 0),
                            'lost_amount': detail_row.get('ปรับหายแต่ละชิ้น', 0),
                            'lost_qty': detail_row.get('จำนวนสินค้าปรับหาย', 0),
                            'price_per_unit': detail_row.get('ราคาสินค้าต่อชิ้น', 0),
                        }
                        DetailModel.sudo().create(detail_vals)

            conn.close()

            _logger.info('Created/Updated %d lost invoices for partner_vat: %s', len(created_ids), partner_vat)
            _logger.info('========== BAANKHIEW LOST FETCH END ==========')

        except Exception as e:
            _logger.error('========== BAANKHIEW LOST FETCH ERROR ==========')
            _logger.error('Error fetching lost invoices from Baankhiew: %s', str(e))
            _logger.exception(e)

        return created_ids


class NpdDebtTrackingBaankhiewLostDetail(models.Model):
    """Model สำหรับเก็บรายการสินค้าที่ปรับหาย"""
    _name = 'npd.debt.tracking.baankhiew.lost.detail'
    _description = 'รายการสินค้าปรับหาย'
    _order = 'product_name'

    lost_invoice_id = fields.Many2one('npd.debt.tracking.baankhiew.lost.invoice', string='ใบแจ้งหนี้ค่าปรับหาย',
        required=True, ondelete='cascade')
    
    rentd_id = fields.Char(string='เลขที่เอกสาร')
    product_id = fields.Char(string='รหัสสินค้า')
    product_name = fields.Char(string='ชื่อสินค้า')
    weight = fields.Float(string='น้ำหนัก')
    lost_amount = fields.Float(string='ปรับหายแต่ละชิ้น')
    lost_qty = fields.Float(string='จำนวนสินค้าปรับหาย')
    price_per_unit = fields.Float(string='ราคาสินค้าต่อชิ้น')



class NpdDebtTrackingBaankhiewTaxInvoice(models.Model):
    """Model สำหรับเก็บข้อมูลค่า Tax จากบ้านเขียว"""
    _name = 'npd.debt.tracking.baankhiew.tax.invoice'
    _description = 'ใบแจ้งหนี้ค่า Tax จากบ้านเขียว'
    _order = 'branch_name, cus_fullname, invoice_number'
    _rec_name = 'invoice_number'

    customer_id = fields.Char(string='ID ลูกค้า')
    cus_fullname = fields.Char(string='ชื่อลูกค้า')
    cus_tel = fields.Char(string='เบอร์ลูกค้า')
    cus_address = fields.Char(string='ที่อยู่ลูกค้า')
    cus_cpnname = fields.Char(string='ชื่อบริษัท')
    cus_cpntel = fields.Char(string='เบอร์บริษัท')
    cus_cpnadd = fields.Char(string='ที่อยู่บริษัท')
    cus_cpntaxid = fields.Char(string='เลขประจำตัวผู้เสียภาษี')
    cus_cpnprovince = fields.Char(string='จังหวัดบริษัท')
    cus_cpnzipcode = fields.Char(string='รหัสไปรษณีย์บริษัท')

    branch_name = fields.Char(string='สาขา')
    invoice_number = fields.Char(string='เลขที่ใบกำกับเช่า')
    arh_num = fields.Char(string='เลขที่ AR (Unique)')

    amount = fields.Float(string='ค่าเช่า')
    vat = fields.Float(string='Vat')
    tax = fields.Float(string='Tax')
    insure = fields.Float(string='ค่าประกัน')
    lost = fields.Float(string='ค่าปรับหาย')
    transport = fields.Float(string='ค่าขนส่ง')

    total_debt = fields.Float(string='หนี้รวม')
    total_paid = fields.Float(string='ยอดรับชำระ')
    remaining_balance = fields.Float(string='ค้างชำระสุทธิ')

    arh_date = fields.Date(string='วันที่เริ่มหนี้')
    due_date = fields.Date(string='วันที่ครบกำหนดชำระ')
    debt_duration = fields.Integer(string='ระยะเวลาที่เป็นหนี้ (วัน)')
    responsible_party = fields.Char(string='ผู้รับผิดชอบ')
    bill_status = fields.Char(string='สถานะบิล')

    def name_get(self):
        """แสดงเฉพาะเลขเอกสารเท่านั้น"""
        result = []
        for rec in self:
            name = rec.invoice_number or 'N/A'
            result.append((rec.id, name))
        return result

    @api.model
    def _get_tax_query(self):
        """Query สำหรับดึงข้อมูลค่า Tax จากบ้านเขียว (tax > 0)"""
        return """
        SELECT
            d.customer_id,
            d.arh_num AS arh_num,
            d.ลูกค้า AS cus_fullname,
            d.เบอร์ติดต่อ AS cus_tel,
            d.ที่อยู่ลูกค้า AS cus_address,
            d.บริษัท AS cus_cpnname,
            d.เบอร์บริษัท AS cus_cpntel,
            d.ที่อยู่บริษัท AS cus_cpnadd,
            d.เลขภาษี AS cus_cpntaxid,
            d.จังหวัดบริษัท AS cus_cpnprovince,
            d.รหัสไปรษณีย์บริษัท AS cus_cpnzipcode,
            d.สาขา AS branch_name,
            d.เลขที่ใบกำกับเช่า AS invoice_number,
            d.ค่าเช่า AS amount,
            d.Vat AS vat,
            d.tax AS tax,
            d.ค่าประกัน AS insure,
            d.ค่าปรับหาย AS lost,
            d.ค่าขนส่ง AS transport,
            d.หนี้รวม AS total_debt,
            COALESCE(p.รับชำระ, 0) AS total_paid,
            d.หนี้รวม - COALESCE(p.รับชำระ, 0) AS remaining_balance,
            d.วันที่เริ่มหนี้ AS arh_date,
            d.วันที่ครบกำหนดชำระ AS due_date,
            DATEDIFF(CURDATE(), d.วันที่เริ่มหนี้) AS debt_duration,
            CASE
                WHEN DATEDIFF(CURDATE(), d.วันที่เริ่มหนี้) BETWEEN 0 AND 45 THEN 'สาขา & sales'
                WHEN DATEDIFF(CURDATE(), d.วันที่เริ่มหนี้) BETWEEN 46 AND 90 THEN 'ส่วนกลาง'
                WHEN DATEDIFF(CURDATE(), d.วันที่เริ่มหนี้) > 90
                    AND (d.หนี้รวม - COALESCE(p.รับชำระ, 0)) >= 500000 THEN 'นิติกร'
                WHEN DATEDIFF(CURDATE(), d.วันที่เริ่มหนี้) > 90
                    AND (d.หนี้รวม - COALESCE(p.รับชำระ, 0)) < 500000 THEN 'ส่วนกลาง'
                ELSE 'ไม่ระบุ'
            END AS responsible_party,
            CASE
                WHEN d.bill_status = 'N' THEN 'ยังไม่ปิดบิล'
                WHEN d.bill_status = 'Y' THEN 'ปิดบิล'
                ELSE 'ไม่มีข้อมูล'
            END AS bill_status_display
        FROM
            (SELECT
                c.cus_id AS customer_id,
                c.cus_fullname AS ลูกค้า,
                c.cus_cpnname AS บริษัท,
                c.cus_tel AS เบอร์ติดต่อ,
                c.cus_address AS ที่อยู่ลูกค้า,
                c.cus_cpnadd AS ที่อยู่บริษัท,
                c.cus_cpntel AS เบอร์บริษัท,
                c.cus_cpntaxid AS เลขภาษี,
                c.cus_cpnprovince AS จังหวัดบริษัท,
                c.cus_cpnzipcode AS รหัสไปรษณีย์บริษัท,
                b.branch_name AS สาขา,
                b.branch_id AS branch_id,
                h.num AS arh_num,
                r.renth_id AS เลขที่ใบกำกับเช่า,
                COALESCE(h.arh_amount, 0) AS ค่าเช่า,
                COALESCE(h.arh_vat, 0) AS Vat,
                COALESCE(h.arh_tax, 0) AS tax,
                COALESCE(h.arh_insure, 0) AS ค่าประกัน,
                COALESCE(h.arh_lost, 0) AS ค่าปรับหาย,
                COALESCE(h.arh_transport, 0) AS ค่าขนส่ง,
                COALESCE(h.arh_amount,0) + COALESCE(h.arh_vat,0) +
                    COALESCE(h.arh_tax,0) + COALESCE(h.arh_insure,0) +
                    COALESCE(h.arh_lost,0) + COALESCE(h.arh_transport,0) +
                    COALESCE(h.arh_broken,0) AS หนี้รวม,
                h.arh_date AS วันที่เริ่มหนี้,
                COALESCE(r.renth_date_return, r.renth_dateend) AS วันที่ครบกำหนดชำระ,
                r.renth_return AS bill_status
            FROM npd_db.ar_head h
            JOIN npd_db.master_customer c ON TRIM(h.arh_cusid) = TRIM(c.cus_id)
            JOIN npd_db.master_branch b ON TRIM(h.branchid) = TRIM(b.branch_id)
            LEFT JOIN npd_db.rentorder_head r ON TRIM(h.arh_docid) = TRIM(r.renth_id)
            WHERE h.cancel = 'N'
            ) d
        LEFT JOIN
            (SELECT
                arh_num,
                SUM(
                    COALESCE(arp_amount, 0) + COALESCE(arp_vat, 0) +
                    COALESCE(arp_tax, 0) + COALESCE(arp_insure, 0) +
                    COALESCE(arp_lost, 0) + COALESCE(arp_broken, 0) +
                    COALESCE(arp_transport, 0)
                ) AS รับชำระ
            FROM npd_db.ar_repay
            WHERE cancel = 'N'
            GROUP BY arh_num
            ) p ON d.arh_num = p.arh_num
        WHERE d.หนี้รวม - COALESCE(p.รับชำระ, 0) > 0
            AND d.tax > 0
            AND d.เลขภาษี = %s
        ORDER BY d.สาขา, d.ลูกค้า, d.เลขที่ใบกำกับเช่า
        """

    @api.model
    def fetch_tax_invoices_by_customer(self, partner_vat):
        """ดึงข้อมูลค่า Tax จากฐานข้อมูลบ้านเขียวตามเลขประจำตัวผู้เสียภาษี
        Returns: list of tax invoice record IDs
        """
        if not partner_vat:
            _logger.warning('fetch_tax_invoices_by_customer: No partner_vat provided')
            return []

        created_ids = []
        _logger.info('========== BAANKHIEW TAX FETCH START ==========')
        _logger.info('Partner VAT from Odoo: [%s]', partner_vat)

        try:
            # ใช้ connection เดียวกับ invoice model
            InvoiceModel = self.env['npd.debt.tracking.baankhiew.invoice']
            conn = InvoiceModel._get_mysql_connection()
            cursor = conn.cursor()

            # ค้นหาด้วยเลขประจำตัวผู้เสียภาษี
            search_vat = partner_vat.strip()
            _logger.info('Searching tax by cus_cpntaxid: [%s]', search_vat)

            query = self._get_tax_query()
            cursor.execute(query, (search_vat,))
            results = cursor.fetchall()

            conn.close()

            _logger.info('Total tax results found: %d', len(results))
            if results:
                for i, r in enumerate(results[:3]):
                    _logger.info('Tax Result %d: cus_fullname=[%s], invoice_number=[%s], tax=[%s], cus_cpntaxid=[%s]',
                               i+1, r.get('cus_fullname'), r.get('invoice_number'), r.get('tax'), r.get('cus_cpntaxid'))

            # ลบข้อมูลเก่าของลูกค้าก่อนดึงใหม่ (ใช้ cus_cpntaxid)
            if results:
                tax_ids = list(set([r.get('cus_cpntaxid') for r in results if r.get('cus_cpntaxid')]))
                if tax_ids:
                    old_records = self.search([('cus_cpntaxid', 'in', tax_ids)])
                    if old_records:
                        _logger.info('Deleting %d old tax records for tax IDs: %s', len(old_records), tax_ids)
                        old_records.sudo().unlink()

            # สร้างข้อมูลใหม่
            for row in results:
                remaining = row.get('remaining_balance', 0) or 0
                # ข้ามถ้ายอดคงเหลือเป็น 0 หรือติดลบ
                if remaining <= 0:
                    _logger.info('Skipping invoice_number=[%s] because remaining_balance=[%s] <= 0', 
                               row.get('invoice_number'), remaining)
                    continue

                vals = {
                    'customer_id': row.get('customer_id'),
                    'arh_num': row.get('arh_num'),
                    'cus_fullname': row.get('cus_fullname'),
                    'cus_tel': row.get('cus_tel'),
                    'cus_address': row.get('cus_address'),
                    'cus_cpnname': row.get('cus_cpnname'),
                    'cus_cpntel': row.get('cus_cpntel'),
                    'cus_cpnadd': row.get('cus_cpnadd'),
                    'cus_cpntaxid': row.get('cus_cpntaxid'),
                    'cus_cpnprovince': row.get('cus_cpnprovince'),
                    'cus_cpnzipcode': row.get('cus_cpnzipcode'),
                    'branch_name': row.get('branch_name'),
                    'invoice_number': row.get('invoice_number'),
                    'amount': row.get('amount', 0),
                    'vat': row.get('vat', 0),
                    'tax': row.get('tax', 0),
                    'insure': row.get('insure', 0),
                    'lost': row.get('lost', 0),
                    'transport': row.get('transport', 0),
                    'total_debt': row.get('total_debt', 0),
                    'total_paid': row.get('total_paid', 0),
                    'remaining_balance': remaining,
                    'arh_date': row.get('arh_date'),
                    'due_date': row.get('due_date'),
                    'debt_duration': row.get('debt_duration', 0),
                    'responsible_party': row.get('responsible_party'),
                    'bill_status': row.get('bill_status_display'),
                }
                new_rec = self.sudo().create(vals)
                created_ids.append(new_rec.id)

            _logger.info('Created/Updated %d tax invoices for partner_vat: %s', len(created_ids), partner_vat)
            _logger.info('========== BAANKHIEW TAX FETCH END ==========')

        except Exception as e:
            _logger.error('========== BAANKHIEW TAX FETCH ERROR ==========')
            _logger.error('Error fetching tax invoices from Baankhiew: %s', str(e))
            _logger.exception(e)

        return created_ids
