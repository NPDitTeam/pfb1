# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from calendar import monthrange
from datetime import date as dt_date
import logging

_logger = logging.getLogger(__name__)


class CommissionReportAPI(http.Controller):
    """
    API Controller สำหรับรายงานค่าคอมมิชชั่น
    - รายงานค่าคอมสาขา (Branch Commission) ดึงจาก SQL โดยตรง
    - รายงานค่าคอม Sales (Sales Commission) ดึงจาก SQL โดยตรง
    """

    # ========================================================
    # API 1: รายงานค่าคอมสาขา (Branch Commission Report)
    # ========================================================
    @http.route('/api/commission/branch', type='json', auth='user', methods=['POST'], csrf=False)
    def get_branch_commission(self, **kwargs):
        """
        รายงานค่าคอมสาขา - ดึงจาก SQL โดยตรง

        Request Body (JSON):
        {
            "month": 1,          // เดือน (1-12) - required
            "year": 2025,        // ปี ค.ศ. - required
            "branch_id": 1       // ID สาขา (optional, เว้นว่างแสดงทุกสาขา)
        }
        """
        try:
            params = request.jsonrequest or {}
            if 'params' in params:
                params = params['params']

            month = params.get('month') or kwargs.get('month')
            year = params.get('year') or kwargs.get('year')
            branch_id = params.get('branch_id') or kwargs.get('branch_id', False)

            if not month or not year:
                return {'status': 'error', 'message': 'กรุณาระบุ month และ year'}

            month = int(month)
            year = int(year)

            if month < 1 or month > 12:
                return {'status': 'error', 'message': 'month ต้องอยู่ระหว่าง 1-12'}

            date_from = dt_date(year, month, 1)
            last_day = monthrange(year, month)[1]
            date_to = dt_date(year, month, last_day)

            # ✅ ใช้เมธอดกลางตัวเดียวกับรายงาน (npd.commission.report) → payroll = รายงานเสมอ
            rows = request.env['npd.commission.report'].sudo()._compute_branch_data(date_from, date_to)
            result = []
            for r in rows:
                br_id = r.get('branch_id')
                if branch_id and br_id != int(branch_id):
                    continue
                branch_rec = request.env['res.branch'].sudo().browse(br_id) if br_id else None
                result.append({
                    'date_from': str(date_from),
                    'date_to': str(date_to),
                    'branch_id': br_id,
                    'branch_name': (branch_rec.name if branch_rec else '') or '',
                    'rental_amount': float(r.get('rental_amount') or 0),
                    'payment_received': float(r.get('payment_received') or 0),
                    'outstanding_debt': float(r.get('outstanding_debt') or 0),
                    'total_expense': float(r.get('total_expense') or 0),
                    'net_rental': float(r.get('net_rental') or 0),
                })
            return {
                'status': 'success',
                'month': month,
                'year': year,
                'count': len(result),
                'data': result,
            }

            # ===== [DEPRECATED] โค้ดเดิม raw SQL ปิดการใช้งานแล้ว (แทนด้วยเมธอดกลางด้านบน) =====
            # เงื่อนไข branch_id (optional)
            branch_filter_rental = ""
            branch_filter_outstanding = ""
            branch_filter_payment = ""
            branch_filter_vendor = ""
            branch_filter_advance = ""
            branch_filter_voucher = ""
            branch_filter_credit_note = ""
            sql_params = {
                'date_from': str(date_from),
                'date_to': str(date_to),
            }

            if branch_id:
                branch_id = int(branch_id)
                branch_filter_rental = "AND am.branch_id = %(branch_id)s"
                branch_filter_outstanding = "AND am.branch_id = %(branch_id)s"
                branch_filter_payment = "AND rb.id = %(branch_id)s"
                branch_filter_vendor = "AND bill.branch_id = %(branch_id)s"
                branch_filter_advance = "AND aaa.branch_id = %(branch_id)s"
                branch_filter_voucher = "AND aaa.branch_id = %(branch_id)s"
                branch_filter_credit_note = "AND am.branch_id = %(branch_id)s"
                sql_params['branch_id'] = branch_id

            # เงื่อนไข payment_state สำหรับใบลดหนี้
            # เดือน 1 ปีปัจจุบัน → ไม่กรอง, เดือนอื่น → payment_state = 'paid'
            current_year = dt_date.today().year
            if month == 1 and year == current_year:
                cn_payment_state_filter = ""
            else:
                cn_payment_state_filter = "AND am.payment_state = 'paid'"

            query = """
                WITH rental AS (
                    SELECT
                        rb.id AS branch_id,
                        rb.name AS branch_name,
                        SUM(am.amount_untaxed) AS rental_amount
                    FROM account_move am
                    LEFT JOIN account_journal aj ON am.journal_id = aj.id
                    LEFT JOIN res_branch rb ON am.branch_id = rb.id
                    WHERE aj.name IN ('สมุดรายวันเช่า(สาขา)', 'สมุดรายวันค่าปรับหาย', 'สมุดรายวันค่าปรับชำรุด')
                        AND am.state = 'posted'
                        AND am.move_type = 'out_invoice'
                        AND am.contact_type = 'branch'
                        AND am.invoice_date >= %(date_from)s
                        AND am.invoice_date <= %(date_to)s
                        {branch_filter_rental}
                    GROUP BY rb.id, rb.name
                ),
                outstanding AS (
                    SELECT
                        rb.id AS branch_id,
                        rb.name AS branch_name,
                        SUM(am.amount_residual / 1.07) AS outstanding_debt
                    FROM account_move am
                    LEFT JOIN account_journal aj ON am.journal_id = aj.id
                    LEFT JOIN res_branch rb ON am.branch_id = rb.id
                    WHERE aj.name IN ('สมุดรายวันเช่า(สาขา)', 'สมุดรายวันค่าปรับหาย', 'สมุดรายวันค่าปรับชำรุด')
                        AND am.state = 'posted'
                        AND am.move_type = 'out_invoice'
                        AND am.payment_state IN ('not_paid', 'partial')
                        AND am.contact_type = 'branch'
                        AND am.invoice_date >= %(date_from)s
                        AND am.invoice_date <= %(date_to)s
                        {branch_filter_outstanding}
                    GROUP BY rb.id, rb.name
                ),
                payment AS (
                    SELECT
                        sub.branch_id,
                        sub.branch_name,
                        SUM(sub.payment_amount) AS payment_received
                    FROM (
                        SELECT DISTINCT
                            ap.id AS payment_id,
                            rb.id AS branch_id,
                            rb.name AS branch_name,
                            CASE WHEN aj.name = 'สมุดรายวันรับชำระค่าปรับชำรุด' THEN ap.amount ELSE ap.amount / 1.07 END AS payment_amount
                        FROM account_payment ap
                        LEFT JOIN account_move am ON ap.move_id = am.id
                        LEFT JOIN account_journal aj ON am.journal_id = aj.id
                        LEFT JOIN res_branch rb ON ap.branch_id = rb.id
                        LEFT JOIN account_move_line aml ON aml.payment_id = ap.id
                        LEFT JOIN account_partial_reconcile apr ON apr.credit_move_id = aml.id OR apr.debit_move_id = aml.id
                        LEFT JOIN account_move_line aml2 ON (apr.debit_move_id = aml2.id OR apr.credit_move_id = aml2.id) AND aml2.id != aml.id
                        LEFT JOIN account_move inv ON aml2.move_id = inv.id AND inv.move_type = 'out_invoice'
                        WHERE aj.name IN ('สมุดรายวันรับชำระ', 'สมุดรายวันรับชำระค่าปรับหาย', 'สมุดรายวันรับชำระค่าปรับชำรุด')
                            AND am.state = 'posted'
                            AND am.date >= %(date_from)s
                            AND am.date <= %(date_to)s
                            AND inv.invoice_date IS NOT NULL
                            AND inv.contact_type = 'branch'
                            AND (EXTRACT(MONTH FROM am.date) != EXTRACT(MONTH FROM inv.invoice_date)
                                 OR EXTRACT(YEAR FROM am.date) != EXTRACT(YEAR FROM inv.invoice_date))
                            AND am.date > inv.invoice_date
                            {branch_filter_payment}
                    ) sub
                    GROUP BY sub.branch_id, sub.branch_name
                ),
                vendor_bills_expense AS (
                    SELECT
                        rb.id AS branch_id,
                        rb.name AS branch_name,
                        SUM(apr.amount) AS vendor_expense
                    FROM account_move bill
                    LEFT JOIN res_branch rb ON bill.branch_id = rb.id
                    LEFT JOIN account_move_line aml ON aml.move_id = bill.id AND aml.credit > 0
                    LEFT JOIN account_partial_reconcile apr ON apr.credit_move_id = aml.id
                    WHERE bill.state = 'posted'
                        AND bill.move_type IN ('in_invoice', 'in_refund')
                        AND bill.invoice_date >= %(date_from)s
                        AND bill.invoice_date <= %(date_to)s
                        AND apr.amount IS NOT NULL
                        {branch_filter_vendor}
                    GROUP BY rb.id, rb.name
                ),
                advance_clear_expense AS (
                    SELECT
                        aaa.branch_id AS branch_id,
                        rb.name AS branch_name,
                        SUM(
                            CASE
                                WHEN EXISTS (
                                    SELECT 1 FROM account_tax_advance_clear_line_rel rel
                                    JOIN account_tax at ON rel.account_tax_id = at.id
                                    WHERE rel.advance_clear_line_id = acl.id
                                    AND at.name LIKE '%%ภาษีซื้อรวม Vat 7%%'
                                ) THEN acl.price_unit
                                WHEN EXISTS (
                                    SELECT 1 FROM account_tax_advance_clear_line_rel rel
                                    JOIN account_tax at ON rel.account_tax_id = at.id
                                    WHERE rel.advance_clear_line_id = acl.id
                                    AND at.name LIKE '%%ภาษีซื้อไม่รวม Vat 7%%'
                                ) THEN acl.price_unit * 1.07
                                WHEN NOT EXISTS (
                                    SELECT 1 FROM account_tax_advance_clear_line_rel rel
                                    WHERE rel.advance_clear_line_id = acl.id
                                ) THEN acl.price_subtotal
                                ELSE 0
                            END
                        ) AS advance_expense
                    FROM account_advance_clear aac
                    JOIN advance_clear_line acl ON acl.advance_clear_id = aac.id
                    JOIN account_analytic_account aaa ON acl.account_analytic_id = aaa.id
                    JOIN res_branch rb ON aaa.branch_id = rb.id
                    WHERE aac.state = 'post'
                        AND aac.doc_date >= %(date_from)s
                        AND aac.doc_date <= %(date_to)s
                        AND aaa.branch_id IS NOT NULL
                        {branch_filter_advance}
                    GROUP BY aaa.branch_id, rb.name
                ),
                voucher_expense AS (
                    -- จาก account.voucher.line: payment_date + analytic.branch + tax-aware VAT
                    -- ภาษีซื้อรวม/ไม่รวม Vat7 = price_subtotal x 1.07 / อื่นๆ/ไม่มี = price_subtotal
                    SELECT
                        aaa.branch_id AS branch_id,
                        rb.name AS branch_name,
                        SUM(CASE WHEN EXISTS (
                                SELECT 1 FROM account_tax_account_voucher_line_rel rel
                                JOIN account_tax at ON rel.account_tax_id = at.id
                                WHERE rel.account_voucher_line_id = avl.id
                                  AND at.name IN ('ภาษีซื้อรวม Vat 7%%', 'ภาษีซื้อไม่รวม Vat 7%%')
                            ) THEN avl.price_subtotal * 1.07
                            ELSE avl.price_subtotal END) AS voucher_expense
                    FROM account_voucher av
                    JOIN account_voucher_line avl ON avl.voucher_id = av.id
                    JOIN account_analytic_account aaa ON avl.account_analytic_id = aaa.id
                    JOIN res_branch rb ON rb.id = aaa.branch_id
                    WHERE av.state IN ('posted', 'transferred')
                        AND av.voucher_type = 'purchase'
                        AND av.check_show IS NOT TRUE
                        AND avl.payment_date >= %(date_from)s
                        AND avl.payment_date <= %(date_to)s
                        AND aaa.branch_id IS NOT NULL
                        {branch_filter_voucher}
                    GROUP BY aaa.branch_id, rb.name
                ),
                credit_note_expense AS (
                    SELECT
                        rb.id AS branch_id,
                        rb.name AS branch_name,
                        SUM(am.amount_untaxed) AS credit_note_amount
                    FROM account_move am
                    LEFT JOIN account_journal aj ON am.journal_id = aj.id
                    LEFT JOIN res_branch rb ON am.branch_id = rb.id
                    WHERE aj.name = 'สมุดรายวันลดหนี้ขาย'
                        AND am.state = 'posted'
                        AND am.move_type = 'out_refund'
                        AND am.contact_type = 'branch'
                        AND am.invoice_date >= %(date_from)s
                        AND am.invoice_date <= %(date_to)s
                        {cn_payment_state_filter}
                        {branch_filter_credit_note}
                    GROUP BY rb.id, rb.name
                ),
                all_branches AS (
                    SELECT DISTINCT branch_id, branch_name
                    FROM (
                        SELECT branch_id, branch_name FROM rental WHERE branch_id IS NOT NULL
                        UNION ALL
                        SELECT branch_id, branch_name FROM outstanding WHERE branch_id IS NOT NULL
                        UNION ALL
                        SELECT branch_id, branch_name FROM payment WHERE branch_id IS NOT NULL
                        UNION ALL
                        SELECT branch_id, branch_name FROM vendor_bills_expense WHERE branch_id IS NOT NULL
                        UNION ALL
                        SELECT branch_id, branch_name FROM advance_clear_expense WHERE branch_id IS NOT NULL
                        UNION ALL
                        SELECT branch_id, branch_name FROM voucher_expense WHERE branch_id IS NOT NULL
                        UNION ALL
                        SELECT branch_id, branch_name FROM credit_note_expense WHERE branch_id IS NOT NULL
                    ) sub
                )
                SELECT
                    ab.branch_id,
                    ab.branch_name,
                    TRUNC((COALESCE(r.rental_amount, 0) - COALESCE(cn.credit_note_amount, 0))::numeric, 2) AS rental_amount,
                    TRUNC(COALESCE(p.payment_received, 0)::numeric, 2) AS payment_received,
                    TRUNC(COALESCE(o.outstanding_debt, 0)::numeric, 2) AS outstanding_debt,
                    TRUNC((COALESCE(vb.vendor_expense, 0) + COALESCE(ac.advance_expense, 0) + COALESCE(v.voucher_expense, 0))::numeric, 2) AS total_expense,
                    TRUNC(((COALESCE(r.rental_amount, 0) - COALESCE(cn.credit_note_amount, 0)) + COALESCE(p.payment_received, 0) - COALESCE(o.outstanding_debt, 0) - (COALESCE(vb.vendor_expense, 0) + COALESCE(ac.advance_expense, 0) + COALESCE(v.voucher_expense, 0)))::numeric, 2) AS net_rental
                FROM all_branches ab
                LEFT JOIN rental r ON ab.branch_id = r.branch_id
                LEFT JOIN outstanding o ON ab.branch_id = o.branch_id
                LEFT JOIN payment p ON ab.branch_id = p.branch_id
                LEFT JOIN vendor_bills_expense vb ON ab.branch_id = vb.branch_id
                LEFT JOIN advance_clear_expense ac ON ab.branch_id = ac.branch_id
                LEFT JOIN voucher_expense v ON ab.branch_id = v.branch_id
                LEFT JOIN credit_note_expense cn ON ab.branch_id = cn.branch_id
                WHERE ab.branch_name IS NOT NULL
                ORDER BY ab.branch_id
                """.format(
                branch_filter_rental=branch_filter_rental,
                branch_filter_outstanding=branch_filter_outstanding,
                branch_filter_payment=branch_filter_payment,
                branch_filter_vendor=branch_filter_vendor,
                branch_filter_advance=branch_filter_advance,
                branch_filter_voucher=branch_filter_voucher,
                branch_filter_credit_note=branch_filter_credit_note,
                cn_payment_state_filter=cn_payment_state_filter,
            )

            cr = request.env.cr
            cr.execute(query, sql_params)
            rows = cr.dictfetchall()

            result = []
            for row in rows:
                result.append({
                    'date_from': str(date_from),
                    'date_to': str(date_to),
                    'branch_id': row['branch_id'],
                    'branch_name': row['branch_name'] or '',
                    'rental_amount': float(row['rental_amount']),
                    'payment_received': float(row['payment_received']),
                    'outstanding_debt': float(row['outstanding_debt']),
                    'total_expense': float(row['total_expense']),
                    'net_rental': float(row['net_rental']),
                })

            return {
                'status': 'success',
                'month': month,
                'year': year,
                'count': len(result),
                'data': result,
            }

        except Exception as e:
            _logger.exception("Error in branch commission API")
            return {'status': 'error', 'message': str(e)}

    # ========================================================
    # API 2: รายงานค่าคอม Sales (Sales Commission Report)
    # ========================================================
    @http.route('/api/commission/sales', type='json', auth='user', methods=['POST'], csrf=False)
    def get_sales_commission(self, **kwargs):
        """
        รายงานค่าคอม Sales - ดึงจาก SQL โดยตรง

        Request Body (JSON):
        {
            "month": 1,          // เดือน (1-12) - required
            "year": 2025,        // ปี ค.ศ. - required
            "sales_contact_id": 5  // ID ของ sales (optional, เว้นว่างแสดงทั้งหมด)
            "branch_id": 1       // ID สาขา (optional, เว้นว่างแสดงทุกสาขา)
        }
        """
        try:
            params = request.jsonrequest or {}
            if 'params' in params:
                params = params['params']

            month = params.get('month') or kwargs.get('month')
            year = params.get('year') or kwargs.get('year')
            sales_contact_id = params.get('sales_contact_id') or kwargs.get('sales_contact_id', False)
            branch_id = params.get('branch_id') or kwargs.get('branch_id', False)

            if not month or not year:
                return {'status': 'error', 'message': 'กรุณาระบุ month และ year'}

            month = int(month)
            year = int(year)

            if month < 1 or month > 12:
                return {'status': 'error', 'message': 'month ต้องอยู่ระหว่าง 1-12'}

            date_from = dt_date(year, month, 1)
            last_day = monthrange(year, month)[1]
            date_to = dt_date(year, month, last_day)

            # ✅ ใช้เมธอดกลางตัวเดียวกับรายงาน (npd.commission.report.sales) → payroll = รายงานเสมอ
            rows = request.env['npd.commission.report.sales'].sudo()._compute_sales_data(date_from, date_to)
            result = []
            for r in rows:
                sc_id = r.get('sales_contact_id')
                br_id = r.get('branch_id')
                if sales_contact_id and sc_id != int(sales_contact_id):
                    continue
                if branch_id and br_id != int(branch_id):
                    continue
                sales_user = request.env['res.users'].sudo().browse(sc_id) if sc_id else None
                branch_rec = request.env['res.branch'].sudo().browse(br_id) if br_id else None
                result.append({
                    'date_from': str(date_from),
                    'date_to': str(date_to),
                    'sales_contact_id': sc_id,
                    'sales_contact_name': (sales_user.partner_id.name if sales_user else '') or '',
                    'employee_code': (sales_user.employee_code if sales_user else '') or '',
                    'branch_id': br_id,
                    'branch_name': (branch_rec.name if branch_rec else '') or '',
                    'rental_amount': float(r.get('rental_amount') or 0),
                    'payment_received': float(r.get('payment_received') or 0),
                    'outstanding_debt': float(r.get('outstanding_debt') or 0),
                    'shipping_cost': float(r.get('shipping_cost') or 0),
                    'net_rental': float(r.get('net_rental') or 0),
                })
            return {
                'status': 'success',
                'month': month,
                'year': year,
                'count': len(result),
                'data': result,
            }

            # ===== [DEPRECATED] โค้ดเดิม raw SQL ปิดการใช้งานแล้ว (แทนด้วยเมธอดกลางด้านบน) =====
            # เงื่อนไข filter (optional)
            sales_filter_rental = ""
            sales_filter_outstanding = ""
            sales_filter_payment = ""
            sales_filter_shipping = ""
            branch_filter_rental = ""
            branch_filter_outstanding = ""
            branch_filter_payment = ""
            branch_filter_shipping = ""
            sql_params = {
                'date_from': str(date_from),
                'date_to': str(date_to),
            }

            if sales_contact_id:
                sales_contact_id = int(sales_contact_id)
                sales_filter_rental = "AND am.sales_contact_id = %(sales_contact_id)s"
                sales_filter_outstanding = "AND am.sales_contact_id = %(sales_contact_id)s"
                sales_filter_payment = "AND inv.sales_contact_id = %(sales_contact_id)s"
                sales_filter_shipping = "AND avl.sales_contact_id = %(sales_contact_id)s"
                sql_params['sales_contact_id'] = sales_contact_id

            if branch_id:
                branch_id = int(branch_id)
                branch_filter_rental = "AND am.branch_id = %(branch_id)s"
                branch_filter_outstanding = "AND am.branch_id = %(branch_id)s"
                branch_filter_payment = "AND inv.branch_id = %(branch_id)s"
                branch_filter_shipping = "AND av.branch_id = %(branch_id)s"
                sql_params['branch_id'] = branch_id

            query = """
            WITH rental AS (
                SELECT
                    am.sales_contact_id,
                    rp.name AS sales_contact_name,
                    rb.id AS branch_id,
                    rb.name AS branch_name,
                    SUM(am.amount_untaxed) AS rental_amount
                FROM account_move am
                LEFT JOIN account_journal aj ON am.journal_id = aj.id
                LEFT JOIN res_branch rb ON am.branch_id = rb.id
                LEFT JOIN res_users ru ON am.sales_contact_id = ru.id
                LEFT JOIN res_partner rp ON ru.partner_id = rp.id
                WHERE aj.name = 'สมุดรายวันเช่า(สาขา)'
                    AND am.state = 'posted'
                    AND am.move_type = 'out_invoice'
                    AND am.contact_type = 'sale'
                    AND am.sales_contact_id IS NOT NULL
                    AND am.invoice_date >= %(date_from)s
                    AND am.invoice_date <= %(date_to)s
                    {sales_filter_rental}
                    {branch_filter_rental}
                GROUP BY am.sales_contact_id, rp.name, rb.id, rb.name
            ),
            outstanding AS (
                SELECT
                    am.sales_contact_id,
                    rp.name AS sales_contact_name,
                    rb.id AS branch_id,
                    rb.name AS branch_name,
                    SUM(am.amount_residual / 1.07) AS outstanding_debt
                FROM account_move am
                LEFT JOIN account_journal aj ON am.journal_id = aj.id
                LEFT JOIN res_branch rb ON am.branch_id = rb.id
                LEFT JOIN res_users ru ON am.sales_contact_id = ru.id
                LEFT JOIN res_partner rp ON ru.partner_id = rp.id
                WHERE aj.name IN ('สมุดรายวันเช่า(สาขา)', 'สมุดรายวันค่าปรับหาย', 'สมุดรายวันค่าปรับชำรุด')
                    AND am.state = 'posted'
                    AND am.move_type = 'out_invoice'
                    AND am.payment_state IN ('not_paid', 'partial')
                    AND am.contact_type = 'sale'
                    AND am.sales_contact_id IS NOT NULL
                    AND am.invoice_date >= %(date_from)s
                    AND am.invoice_date <= %(date_to)s
                    {sales_filter_outstanding}
                    {branch_filter_outstanding}
                GROUP BY am.sales_contact_id, rp.name, rb.id, rb.name
            ),
            payment AS (
                SELECT
                    sub.sales_contact_id,
                    sub.sales_contact_name,
                    sub.branch_id,
                    sub.branch_name,
                    SUM(sub.payment_amount) AS payment_received
                FROM (
                    SELECT DISTINCT
                        ap.id AS payment_id,
                        inv.sales_contact_id,
                        rp.name AS sales_contact_name,
                        rb.id AS branch_id,
                        rb.name AS branch_name,
                        CASE WHEN aj.name = 'สมุดรายวันรับชำระค่าปรับชำรุด' THEN ap.amount ELSE ap.amount / 1.07 END AS payment_amount
                    FROM account_payment ap
                    LEFT JOIN account_move am ON ap.move_id = am.id
                    LEFT JOIN account_journal aj ON am.journal_id = aj.id
                    LEFT JOIN account_move_line aml ON aml.payment_id = ap.id
                    LEFT JOIN account_partial_reconcile apr ON apr.credit_move_id = aml.id OR apr.debit_move_id = aml.id
                    LEFT JOIN account_move_line aml2 ON (apr.debit_move_id = aml2.id OR apr.credit_move_id = aml2.id) AND aml2.id != aml.id
                    LEFT JOIN account_move inv ON aml2.move_id = inv.id AND inv.move_type = 'out_invoice'
                    LEFT JOIN res_branch rb ON inv.branch_id = rb.id
                    LEFT JOIN res_users ru ON inv.sales_contact_id = ru.id
                    LEFT JOIN res_partner rp ON ru.partner_id = rp.id
                    WHERE aj.name IN ('สมุดรายวันรับชำระ', 'สมุดรายวันรับชำระค่าปรับหาย', 'สมุดรายวันรับชำระค่าปรับชำรุด')
                        AND am.state = 'posted'
                        AND am.date >= %(date_from)s
                        AND am.date <= %(date_to)s
                        AND inv.invoice_date IS NOT NULL
                        AND inv.contact_type = 'sale'
                        AND inv.sales_contact_id IS NOT NULL
                        AND (EXTRACT(MONTH FROM am.date) != EXTRACT(MONTH FROM inv.invoice_date)
                             OR EXTRACT(YEAR FROM am.date) != EXTRACT(YEAR FROM inv.invoice_date))
                        AND am.date > inv.invoice_date
                        {sales_filter_payment}
                        {branch_filter_payment}
                ) sub
                GROUP BY sub.sales_contact_id, sub.sales_contact_name, sub.branch_id, sub.branch_name
            ),
            shipping AS (
                SELECT
                    ru.id AS sales_contact_id,
                    rp.name AS sales_contact_name,
                    av.branch_id AS branch_id,
                    rb.name AS branch_name,
                    SUM(avl.price_subtotal) AS shipping_cost
                FROM account_voucher av
                LEFT JOIN account_voucher_line avl ON avl.voucher_id = av.id
                LEFT JOIN res_users ru ON avl.sales_contact_id = ru.id
                LEFT JOIN res_partner rp ON ru.partner_id = rp.id
                LEFT JOIN res_branch rb ON av.branch_id = rb.id
                WHERE av.state IN ('posted', 'transferred')
                    AND av.date >= %(date_from)s
                    AND av.date <= %(date_to)s
                    AND avl.sales_contact_id IS NOT NULL
                    {sales_filter_shipping}
                    {branch_filter_shipping}
                GROUP BY ru.id, rp.name, av.branch_id, rb.name
            ),
            all_sales AS (
                SELECT DISTINCT sales_contact_id, sales_contact_name, branch_id, branch_name FROM rental
                UNION
                SELECT DISTINCT sales_contact_id, sales_contact_name, branch_id, branch_name FROM outstanding
                UNION
                SELECT DISTINCT sales_contact_id, sales_contact_name, branch_id, branch_name FROM payment
                UNION
                SELECT DISTINCT sales_contact_id, sales_contact_name, branch_id, branch_name FROM shipping
            )
            SELECT
                a.sales_contact_id,
                a.sales_contact_name,
                ru.employee_code AS employee_code,
                a.branch_id,
                a.branch_name,
                TRUNC(COALESCE(r.rental_amount, 0)::numeric, 2) AS rental_amount,
                TRUNC(COALESCE(p.payment_received, 0)::numeric, 2) AS payment_received,
                TRUNC(COALESCE(o.outstanding_debt, 0)::numeric, 2) AS outstanding_debt,
                TRUNC(COALESCE(s.shipping_cost, 0)::numeric, 2) AS shipping_cost,
                TRUNC((COALESCE(r.rental_amount, 0) + COALESCE(p.payment_received, 0) - COALESCE(o.outstanding_debt, 0) - COALESCE(s.shipping_cost, 0))::numeric, 2) AS net_rental
            FROM all_sales a
            LEFT JOIN res_users ru ON a.sales_contact_id = ru.id
            LEFT JOIN rental r ON a.sales_contact_id = r.sales_contact_id AND a.branch_id = r.branch_id
            LEFT JOIN outstanding o ON a.sales_contact_id = o.sales_contact_id AND a.branch_id = o.branch_id
            LEFT JOIN payment p ON a.sales_contact_id = p.sales_contact_id AND a.branch_id = p.branch_id
            LEFT JOIN shipping s ON a.sales_contact_id = s.sales_contact_id AND a.branch_id = s.branch_id
            WHERE a.sales_contact_name IS NOT NULL
            ORDER BY a.branch_id, a.sales_contact_name
            """.format(
                sales_filter_rental=sales_filter_rental,
                sales_filter_outstanding=sales_filter_outstanding,
                sales_filter_payment=sales_filter_payment,
                sales_filter_shipping=sales_filter_shipping,
                branch_filter_rental=branch_filter_rental,
                branch_filter_outstanding=branch_filter_outstanding,
                branch_filter_payment=branch_filter_payment,
                branch_filter_shipping=branch_filter_shipping,
            )

            cr = request.env.cr
            cr.execute(query, sql_params)
            rows = cr.dictfetchall()

            result = []
            for row in rows:
                result.append({
                    'date_from': str(date_from),
                    'date_to': str(date_to),
                    'sales_contact_id': row['sales_contact_id'],
                    'sales_contact_name': row['sales_contact_name'] or '',
                    'employee_code': row.get('employee_code') or '',
                    'branch_id': row['branch_id'],
                    'branch_name': row['branch_name'] or '',
                    'rental_amount': float(row['rental_amount']),
                    'payment_received': float(row['payment_received']),
                    'outstanding_debt': float(row['outstanding_debt']),
                    'shipping_cost': float(row['shipping_cost']),
                    'net_rental': float(row['net_rental']),
                })

            return {
                'status': 'success',
                'month': month,
                'year': year,
                'count': len(result),
                'data': result,
            }

        except Exception as e:
            _logger.exception("Error in sales commission API")
            return {'status': 'error', 'message': str(e)}

    # ========================================================
    # API 3: รายงานค่าคอม Sales (จากตาราง npd_sales_commission_report)
    # ========================================================
    @http.route('/api/commission/bankheaw', type='json', auth='user', methods=['POST'], csrf=False)
    def get_sales_commission_report(self, **kwargs):
        """
        รายงานค่าคอม Sales จากตาราง npd_sales_commission_report
        พร้อมสรุปรวมเดือน และสรุปรวมปี

        Request Body (JSON):
        {
            "year": 2025,              // ปี ค.ศ. (optional, เว้นว่างแสดงทั้งหมด)
            "month": 1,               // เดือน 1-12 (optional, เว้นว่างแสดงทั้งหมด)
            "branch_id_odoo": 1,      // รหัสสาขา Odoo (optional)
            "employee_code": "E001"   // รหัสพนักงาน (optional)
        }
        """
        try:
            params = request.jsonrequest or {}
            if 'params' in params:
                params = params['params']

            year = params.get('year') or kwargs.get('year', False)
            month = params.get('month') or kwargs.get('month', False)
            branch_id_odoo = params.get('branch_id_odoo') or kwargs.get('branch_id_odoo', False)
            employee_code = params.get('employee_code') or kwargs.get('employee_code', False)

            # สร้าง filter conditions
            where_clauses = []
            sql_params = {}

            if year:
                year = int(year)
                where_clauses.append("EXTRACT(YEAR FROM report_date_from) = %(year)s")
                sql_params['year'] = year

            if month:
                month = int(month)
                if month < 1 or month > 12:
                    return {'status': 'error', 'message': 'month ต้องอยู่ระหว่าง 1-12'}
                where_clauses.append("EXTRACT(MONTH FROM report_date_from) = %(month)s")
                sql_params['month'] = month

            if branch_id_odoo:
                branch_id_odoo = int(branch_id_odoo)
                where_clauses.append("branch_id_odoo = %(branch_id_odoo)s")
                sql_params['branch_id_odoo'] = branch_id_odoo

            if employee_code:
                where_clauses.append("employee_code = %(employee_code)s")
                sql_params['employee_code'] = str(employee_code).strip()

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            query = """
            SELECT *
            FROM (
                -- ข้อมูลรายละเอียด
                SELECT
                    report_period AS period,
                    CASE WHEN report_type = 'branch' THEN 'สาขา' ELSE 'เซลล์' END AS type,
                    branch_id AS branch_code,
                    branch_id_odoo,
                    branch_name,
                    employee_code,
                    salesperson_name,
                    COALESCE(initial_rent, 0) AS initial_rent,
                    COALESCE(discount, 0) AS discount,
                    COALESCE(rent_difference, 0) AS rent_difference,
                    COALESCE(total_rent_revenue, 0) AS total_rent_revenue,
                    COALESCE(outstanding_bill_count, 0) AS outstanding_bill_count,
                    COALESCE(total_outstanding, 0) AS total_outstanding,
                    COALESCE(total_paid, 0) AS total_paid,
                    COALESCE(net_outstanding, 0) AS net_outstanding,
                    COALESCE(old_debt_paid, 0) AS old_debt_paid,
                    COALESCE(net_total, 0) AS net_total,
                    EXTRACT(YEAR FROM report_date_from) AS year_sort,
                    EXTRACT(MONTH FROM report_date_from) AS month_sort,
                    0 AS sort_order
                FROM npd_sales_commission_report
                {where_sql}

                UNION ALL

                -- สรุปรวมเดือน
                SELECT
                    report_period,
                    '*** รวมเดือน ' || report_period || ' ***',
                    '', NULL, '', '', '',
                    SUM(COALESCE(initial_rent, 0)),
                    SUM(COALESCE(discount, 0)),
                    SUM(COALESCE(rent_difference, 0)),
                    SUM(COALESCE(total_rent_revenue, 0)),
                    SUM(COALESCE(outstanding_bill_count, 0)),
                    SUM(COALESCE(total_outstanding, 0)),
                    SUM(COALESCE(total_paid, 0)),
                    SUM(COALESCE(net_outstanding, 0)),
                    SUM(COALESCE(old_debt_paid, 0)),
                    SUM(COALESCE(net_total, 0)),
                    EXTRACT(YEAR FROM MIN(report_date_from)),
                    EXTRACT(MONTH FROM MIN(report_date_from)),
                    1
                FROM npd_sales_commission_report
                {where_sql}
                GROUP BY report_period

                UNION ALL

                -- สรุปรวมปี
                SELECT
                    EXTRACT(YEAR FROM report_date_from)::text || ' รวมปี',
                    '***** รวมปี ' || EXTRACT(YEAR FROM report_date_from)::text || ' *****',
                    '', NULL, '', '', '',
                    SUM(COALESCE(initial_rent, 0)),
                    SUM(COALESCE(discount, 0)),
                    SUM(COALESCE(rent_difference, 0)),
                    SUM(COALESCE(total_rent_revenue, 0)),
                    SUM(COALESCE(outstanding_bill_count, 0)),
                    SUM(COALESCE(total_outstanding, 0)),
                    SUM(COALESCE(total_paid, 0)),
                    SUM(COALESCE(net_outstanding, 0)),
                    SUM(COALESCE(old_debt_paid, 0)),
                    SUM(COALESCE(net_total, 0)),
                    EXTRACT(YEAR FROM report_date_from),
                    13,
                    2
                FROM npd_sales_commission_report
                {where_sql}
                GROUP BY EXTRACT(YEAR FROM report_date_from)
            ) sub
            ORDER BY year_sort ASC, month_sort ASC, sort_order ASC, branch_code, type, salesperson_name
            """.format(where_sql=where_sql)

            cr = request.env.cr
            cr.execute(query, sql_params)
            rows = cr.dictfetchall()

            result = []
            for row in rows:
                result.append({
                    'period': row['period'] or '',
                    'type': row['type'] or '',
                    'branch_code': row['branch_code'] or '',
                    'branch_id_odoo': row['branch_id_odoo'],
                    'branch_name': row['branch_name'] or '',
                    'employee_code': row['employee_code'] or '',
                    'salesperson_name': row['salesperson_name'] or '',
                    'initial_rent': float(row['initial_rent'] or 0),
                    'discount': float(row['discount'] or 0),
                    'rent_difference': float(row['rent_difference'] or 0),
                    'total_rent_revenue': float(row['total_rent_revenue'] or 0),
                    'outstanding_bill_count': float(row['outstanding_bill_count'] or 0),
                    'total_outstanding': float(row['total_outstanding'] or 0),
                    'total_paid': float(row['total_paid'] or 0),
                    'net_outstanding': float(row['net_outstanding'] or 0),
                    'old_debt_paid': float(row['old_debt_paid'] or 0),
                    'net_total': float(row['net_total'] or 0),
                    'sort_order': int(row['sort_order'] or 0),
                })

            return {
                'status': 'success',
                'year': year or 'all',
                'month': month or 'all',
                'count': len(result),
                'data': result,
            }

        except Exception as e:
            _logger.exception("Error in sales commission report API")
            return {'status': 'error', 'message': str(e)}
