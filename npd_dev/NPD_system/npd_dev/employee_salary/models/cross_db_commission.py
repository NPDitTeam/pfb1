# -*- coding: utf-8 -*-
"""Cross-DB Commission Query Helper

ดึงข้อมูลค่าคอมมิชชั่นจาก DB ปลายทาง (NPD_Intertrading_New, NPD_S_Group_New_V2,
NPD_Bangkok_New, NPD_Steeltech_New) ผ่าน psycopg2 โดยตรง — แทนการเรียก HTTP API
(เดิม https://npderp.com/api/commission/*)

ใช้ SQL ชุดเดียวกับใน npd_commission_report/controllers/commission_api.py
(deprecated section) เพื่อให้ผลลัพธ์ตรงกับ API เป๊ะ ๆ — payroll จะไม่ surprise

คืน list[dict] รูปแบบเดียวกับ response ของ API เดิม → ลด churn ที่ฝั่งผู้เรียก

ตั้งค่า DB list ผ่าน System Parameter:
  npd.commission.cross_db_list  (CSV, default: 4 db ด้านบน)

ตั้งค่า bankheaw db (มี table npd_sales_commission_report) ผ่าน:
  npd.commission.bankheaw_db    (default: 'NPD_S_Group_New_V2')
"""
import logging
import psycopg2
import psycopg2.extras
from odoo import models, api
from odoo.tools import config

_logger = logging.getLogger(__name__)


# ===========================================================
# SQL: Branch Commission (เทียบเท่า /api/commission/branch)
# ============================================================
# คัดลอกตรงจาก commission_api.py deprecated section
# ✅ ตัด branch_filter_* ออก (ฝั่งผู้เรียกกรอง branch_name ใน Python)
# ✅ คงเงื่อนไข payment_state ของใบลดหนี้: เดือน 1 ปีปัจจุบัน → ไม่กรอง
SQL_BRANCH = """
WITH rental AS (
    -- ✅ "ยอดเช่า" นับเฉพาะ "สมุดรายวันเช่า(สาขา)" เท่านั้น (ตรงกับ ORM ของ _compute_branch_data)
    --    ไม่รวมสมุดค่าปรับหาย/ชำรุด — ตัวค่าปรับใช้คำนวณแค่ outstanding (หนี้ค้าง)
    SELECT
        rb.id AS branch_id,
        rb.name AS branch_name,
        SUM(am.amount_untaxed) AS rental_amount
    FROM account_move am
    LEFT JOIN account_journal aj ON am.journal_id = aj.id
    LEFT JOIN res_branch rb ON am.branch_id = rb.id
    WHERE aj.name = 'สมุดรายวันเช่า(สาขา)'
        AND am.state = 'posted'
        AND am.move_type = 'out_invoice'
        AND am.contact_type = 'branch'
        AND am.invoice_date >= %(date_from)s
        AND am.invoice_date <= %(date_to)s
    GROUP BY rb.id, rb.name
),
outstanding AS (
    -- ✅ คำนวณ "หนี้ค้างชำระ ณ date_to" (ไม่ใช่ ณ ปัจจุบัน) — ตรงตาม ORM ของ _compute_branch_data
    --    ที่ใช้ _outstanding_residual_asof(invoice, date_to)
    --    Logic: bal = debit - credit ของ AR line, แล้วหัก paid ที่ counterpart.date <= date_to
    SELECT
        rl.branch_id,
        rb.name AS branch_name,
        SUM(GREATEST(0, rl.balance - COALESCE(p.paid_amount, 0))) / 1.07 AS outstanding_debt
    FROM (
        SELECT
            am.id AS move_id,
            am.branch_id,
            aml.id AS line_id,
            (COALESCE(aml.debit, 0) - COALESCE(aml.credit, 0)) AS balance
        FROM account_move am
        JOIN account_journal aj ON am.journal_id = aj.id
        JOIN account_move_line aml ON aml.move_id = am.id
        JOIN account_account aa ON aa.id = aml.account_id
        WHERE aj.name IN ('สมุดรายวันเช่า(สาขา)', 'สมุดรายวันค่าปรับหาย', 'สมุดรายวันค่าปรับชำรุด')
            AND am.state = 'posted'
            AND am.move_type = 'out_invoice'
            AND am.contact_type = 'branch'
            AND am.invoice_date >= %(date_from)s
            AND am.invoice_date <= %(date_to)s
            AND aa.internal_type = 'receivable'
    ) rl
    LEFT JOIN res_branch rb ON rl.branch_id = rb.id
    LEFT JOIN LATERAL (
        -- รวม payment ที่จับคู่กับ line นี้ โดย counterpart.date <= date_to
        SELECT COALESCE(SUM(amount), 0) AS paid_amount FROM (
            SELECT apr.amount
            FROM account_partial_reconcile apr
            JOIN account_move_line cml ON cml.id = apr.credit_move_id
            JOIN account_move cm ON cm.id = cml.move_id
            WHERE apr.debit_move_id = rl.line_id AND cm.date <= %(date_to)s::date
            UNION ALL
            SELECT apr.amount
            FROM account_partial_reconcile apr
            JOIN account_move_line dml ON dml.id = apr.debit_move_id
            JOIN account_move dm ON dm.id = dml.move_id
            WHERE apr.credit_move_id = rl.line_id AND dm.date <= %(date_to)s::date
        ) sub
    ) p ON TRUE
    GROUP BY rl.branch_id, rb.name
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
            ap.amount / 1.07 AS payment_amount
        FROM account_payment ap
        LEFT JOIN account_move am ON ap.move_id = am.id
        LEFT JOIN account_journal aj ON am.journal_id = aj.id
        LEFT JOIN res_branch rb ON ap.branch_id = rb.id
        LEFT JOIN account_move_line aml ON aml.payment_id = ap.id
        LEFT JOIN account_partial_reconcile apr
            ON apr.credit_move_id = aml.id OR apr.debit_move_id = aml.id
        LEFT JOIN account_move_line aml2
            ON (apr.debit_move_id = aml2.id OR apr.credit_move_id = aml2.id)
            AND aml2.id != aml.id
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
    ) sub
    GROUP BY sub.branch_id, sub.branch_name
),
vendor_bills_expense AS (
    -- ✅ "ยอดที่จ่ายแล้ว" ต่อ bill = amount_total − amount_residual
    --    (สมมูลกับการ sum payment amounts ใน invoice_payments_widget ของ ORM
    --     แต่ widget เป็น computed field ไม่ stored ใน DB จึงใช้ amount_residual แทน)
    SELECT
        rb.id AS branch_id,
        rb.name AS branch_name,
        COALESCE(SUM(
            COALESCE(bill.amount_total, 0) - COALESCE(bill.amount_residual, 0)
        ), 0) AS vendor_expense
    FROM account_move bill
    LEFT JOIN res_branch rb ON bill.branch_id = rb.id
    WHERE bill.state = 'posted'
        AND bill.move_type IN ('in_invoice', 'in_refund')
        AND bill.invoice_date >= %(date_from)s
        AND bill.invoice_date <= %(date_to)s
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
    GROUP BY aaa.branch_id, rb.name
),
voucher_expense AS (
    -- ดึงจาก account.voucher (หัวเอกสาร): branch_id ของหัวเอกสาร + amount (รวม VAT)
    SELECT
        av.branch_id AS branch_id,
        rb.name AS branch_name,
        SUM(av.amount) AS voucher_expense
    FROM account_voucher av
    JOIN res_branch rb ON rb.id = av.branch_id
    WHERE av.state IN ('posted', 'transferred')
        AND av.date >= %(date_from)s
        AND av.date <= %(date_to)s
        AND av.branch_id IS NOT NULL
    GROUP BY av.branch_id, rb.name
),
credit_note_expense AS (
    -- ✅ ไม่ filter payment_state — ตรงกับ ORM ของ _compute_branch_data
    --    (CN ที่ออกในเดือนนั้นถูกหักออกจากยอดเช่า ไม่ว่าจะจ่ายแล้วหรือยัง)
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
    GROUP BY rb.id, rb.name
),
jv_expense AS (
    -- JV (สมุดทั่วไป name ขึ้นต้น JV- , state=posted) SUM(debit) — ตรงกับรายงาน
    SELECT am.branch_id AS branch_id, rb.name AS branch_name,
           COALESCE(SUM(aml.debit), 0) AS jv_expense
    FROM account_move am
    JOIN account_move_line aml ON aml.move_id = am.id
    JOIN res_branch rb ON rb.id = am.branch_id
    WHERE am.state = 'posted'
        AND am.name LIKE 'JV-%%'
        AND am.date >= %(date_from)s
        AND am.date <= %(date_to)s
        AND aml.debit > 0
    GROUP BY am.branch_id, rb.name
),
salary_expense AS (
    -- salary จาก snapshot npd_salary_branch_report_line (กรอง company แล้วต่อ DB)
    -- เดือน/ปี derive จาก date_from
    SELECT rb.id AS branch_id, rb.name AS branch_name,
           COALESCE(SUM(s.total_income), 0) AS salary_expense
    FROM npd_salary_branch_report_line s
    JOIN res_branch rb ON rb.name = s.branch_name
    WHERE s.month = EXTRACT(MONTH FROM %(date_from)s::date)::int
        AND s.year = EXTRACT(YEAR FROM %(date_from)s::date)::text
    GROUP BY rb.id, rb.name
),
all_branches AS (
    SELECT DISTINCT branch_id, branch_name FROM (
        SELECT branch_id, branch_name FROM rental WHERE branch_id IS NOT NULL
        UNION ALL SELECT branch_id, branch_name FROM outstanding WHERE branch_id IS NOT NULL
        UNION ALL SELECT branch_id, branch_name FROM payment WHERE branch_id IS NOT NULL
        UNION ALL SELECT branch_id, branch_name FROM vendor_bills_expense WHERE branch_id IS NOT NULL
        UNION ALL SELECT branch_id, branch_name FROM advance_clear_expense WHERE branch_id IS NOT NULL
        UNION ALL SELECT branch_id, branch_name FROM voucher_expense WHERE branch_id IS NOT NULL
        UNION ALL SELECT branch_id, branch_name FROM credit_note_expense WHERE branch_id IS NOT NULL
        UNION ALL SELECT branch_id, branch_name FROM jv_expense WHERE branch_id IS NOT NULL
        UNION ALL SELECT branch_id, branch_name FROM salary_expense WHERE branch_id IS NOT NULL
    ) sub
)
SELECT
    ab.branch_id,
    ab.branch_name,
    TRUNC((COALESCE(r.rental_amount, 0) - COALESCE(cn.credit_note_amount, 0))::numeric, 2) AS rental_amount,
    TRUNC(COALESCE(p.payment_received, 0)::numeric, 2) AS payment_received,
    TRUNC(COALESCE(o.outstanding_debt, 0)::numeric, 2) AS outstanding_debt,
    TRUNC((
        COALESCE(vb.vendor_expense, 0) + COALESCE(ac.advance_expense, 0)
        + COALESCE(v.voucher_expense, 0) + COALESCE(jv.jv_expense, 0)
        + CASE WHEN (COALESCE(vb.vendor_expense, 0) + COALESCE(ac.advance_expense, 0)
                     + COALESCE(v.voucher_expense, 0) + COALESCE(jv.jv_expense, 0)) > 0
               THEN COALESCE(sal.salary_expense, 0) ELSE 0 END
    )::numeric, 2) AS total_expense,
    TRUNC((
        (COALESCE(r.rental_amount, 0) - COALESCE(cn.credit_note_amount, 0))
        + COALESCE(p.payment_received, 0)
        - COALESCE(o.outstanding_debt, 0)
        - (
            COALESCE(vb.vendor_expense, 0) + COALESCE(ac.advance_expense, 0)
            + COALESCE(v.voucher_expense, 0) + COALESCE(jv.jv_expense, 0)
            + CASE WHEN (COALESCE(vb.vendor_expense, 0) + COALESCE(ac.advance_expense, 0)
                         + COALESCE(v.voucher_expense, 0) + COALESCE(jv.jv_expense, 0)) > 0
                   THEN COALESCE(sal.salary_expense, 0) ELSE 0 END
        )
    )::numeric, 2) AS net_rental
FROM all_branches ab
LEFT JOIN rental r ON ab.branch_id = r.branch_id
LEFT JOIN outstanding o ON ab.branch_id = o.branch_id
LEFT JOIN payment p ON ab.branch_id = p.branch_id
LEFT JOIN vendor_bills_expense vb ON ab.branch_id = vb.branch_id
LEFT JOIN advance_clear_expense ac ON ab.branch_id = ac.branch_id
LEFT JOIN voucher_expense v ON ab.branch_id = v.branch_id
LEFT JOIN credit_note_expense cn ON ab.branch_id = cn.branch_id
LEFT JOIN jv_expense jv ON ab.branch_id = jv.branch_id
LEFT JOIN salary_expense sal ON ab.branch_id = sal.branch_id
WHERE ab.branch_name IS NOT NULL
ORDER BY ab.branch_id
"""

# ============================================================
# SQL: Sales Commission (เทียบเท่า /api/commission/sales)
# ============================================================
SQL_SALES = """
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
    GROUP BY am.sales_contact_id, rp.name, rb.id, rb.name
),
outstanding AS (
    -- ✅ คำนวณ "หนี้ค้างชำระ ณ date_to" (as-of-date) — ตรงกับ _outstanding_residual_asof ของ ORM
    SELECT
        rl.sales_contact_id,
        rp.name AS sales_contact_name,
        rl.branch_id,
        rb.name AS branch_name,
        SUM(GREATEST(0, rl.balance - COALESCE(p.paid_amount, 0))) / 1.07 AS outstanding_debt
    FROM (
        SELECT
            am.id AS move_id,
            am.sales_contact_id,
            am.branch_id,
            aml.id AS line_id,
            (COALESCE(aml.debit, 0) - COALESCE(aml.credit, 0)) AS balance
        FROM account_move am
        JOIN account_journal aj ON am.journal_id = aj.id
        JOIN account_move_line aml ON aml.move_id = am.id
        JOIN account_account aa ON aa.id = aml.account_id
        WHERE aj.name = 'สมุดรายวันเช่า(สาขา)'
            AND am.state = 'posted'
            AND am.move_type = 'out_invoice'
            AND am.contact_type = 'sale'
            AND am.sales_contact_id IS NOT NULL
            AND am.invoice_date >= %(date_from)s
            AND am.invoice_date <= %(date_to)s
            AND aa.internal_type = 'receivable'
    ) rl
    LEFT JOIN res_branch rb ON rl.branch_id = rb.id
    LEFT JOIN res_users ru ON rl.sales_contact_id = ru.id
    LEFT JOIN res_partner rp ON ru.partner_id = rp.id
    LEFT JOIN LATERAL (
        SELECT COALESCE(SUM(amount), 0) AS paid_amount FROM (
            SELECT apr.amount
            FROM account_partial_reconcile apr
            JOIN account_move_line cml ON cml.id = apr.credit_move_id
            JOIN account_move cm ON cm.id = cml.move_id
            WHERE apr.debit_move_id = rl.line_id AND cm.date <= %(date_to)s::date
            UNION ALL
            SELECT apr.amount
            FROM account_partial_reconcile apr
            JOIN account_move_line dml ON dml.id = apr.debit_move_id
            JOIN account_move dm ON dm.id = dml.move_id
            WHERE apr.credit_move_id = rl.line_id AND dm.date <= %(date_to)s::date
        ) sub
    ) p ON TRUE
    GROUP BY rl.sales_contact_id, rp.name, rl.branch_id, rb.name
),
credit_note_sales AS (
    -- ✅ ใบลดหนี้ขาย (out_refund) จับคู่ด้วย (sales_contact_id, branch_id) — ตรงกับ ORM
    SELECT
        am.sales_contact_id,
        am.branch_id,
        SUM(am.amount_untaxed) AS cn_amount
    FROM account_move am
    LEFT JOIN account_journal aj ON am.journal_id = aj.id
    WHERE aj.name = 'สมุดรายวันลดหนี้ขาย'
        AND am.state = 'posted'
        AND am.move_type = 'out_refund'
        AND am.contact_type = 'sale'
        AND am.sales_contact_id IS NOT NULL
        AND am.invoice_date >= %(date_from)s
        AND am.invoice_date <= %(date_to)s
    GROUP BY am.sales_contact_id, am.branch_id
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
            ap.amount / 1.07 AS payment_amount
        FROM account_payment ap
        LEFT JOIN account_move am ON ap.move_id = am.id
        LEFT JOIN account_journal aj ON am.journal_id = aj.id
        LEFT JOIN account_move_line aml ON aml.payment_id = ap.id
        LEFT JOIN account_partial_reconcile apr
            ON apr.credit_move_id = aml.id OR apr.debit_move_id = aml.id
        LEFT JOIN account_move_line aml2
            ON (apr.debit_move_id = aml2.id OR apr.credit_move_id = aml2.id)
            AND aml2.id != aml.id
        LEFT JOIN account_move inv ON aml2.move_id = inv.id AND inv.move_type = 'out_invoice'
        LEFT JOIN res_branch rb ON inv.branch_id = rb.id
        LEFT JOIN res_users ru ON inv.sales_contact_id = ru.id
        LEFT JOIN res_partner rp ON ru.partner_id = rp.id
        WHERE aj.name = 'สมุดรายวันรับชำระ'
            AND am.state = 'posted'
            AND am.date >= %(date_from)s
            AND am.date <= %(date_to)s
            AND inv.invoice_date IS NOT NULL
            AND inv.contact_type = 'sale'
            AND inv.sales_contact_id IS NOT NULL
            AND (EXTRACT(MONTH FROM am.date) != EXTRACT(MONTH FROM inv.invoice_date)
                 OR EXTRACT(YEAR FROM am.date) != EXTRACT(YEAR FROM inv.invoice_date))
            AND am.date > inv.invoice_date
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
    GROUP BY ru.id, rp.name, av.branch_id, rb.name
),
all_sales AS (
    SELECT DISTINCT sales_contact_id, sales_contact_name, branch_id, branch_name FROM rental
    UNION SELECT DISTINCT sales_contact_id, sales_contact_name, branch_id, branch_name FROM outstanding
    UNION SELECT DISTINCT sales_contact_id, sales_contact_name, branch_id, branch_name FROM payment
    UNION SELECT DISTINCT sales_contact_id, sales_contact_name, branch_id, branch_name FROM shipping
)
SELECT
    a.sales_contact_id,
    a.sales_contact_name,
    ru.employee_code AS employee_code,
    a.branch_id,
    a.branch_name,
    -- ✅ rental_amount หัก CN ออกแล้ว (ตรงกับ ORM)
    TRUNC((COALESCE(r.rental_amount, 0) - COALESCE(cn.cn_amount, 0))::numeric, 2) AS rental_amount,
    TRUNC(COALESCE(p.payment_received, 0)::numeric, 2) AS payment_received,
    TRUNC(COALESCE(o.outstanding_debt, 0)::numeric, 2) AS outstanding_debt,
    TRUNC(COALESCE(s.shipping_cost, 0)::numeric, 2) AS shipping_cost,
    TRUNC((
        (COALESCE(r.rental_amount, 0) - COALESCE(cn.cn_amount, 0))
        + COALESCE(p.payment_received, 0)
        - COALESCE(o.outstanding_debt, 0)
        - COALESCE(s.shipping_cost, 0)
    )::numeric, 2) AS net_rental
FROM all_sales a
LEFT JOIN res_users ru ON a.sales_contact_id = ru.id
LEFT JOIN rental r ON a.sales_contact_id = r.sales_contact_id AND a.branch_id = r.branch_id
LEFT JOIN outstanding o ON a.sales_contact_id = o.sales_contact_id AND a.branch_id = o.branch_id
LEFT JOIN payment p ON a.sales_contact_id = p.sales_contact_id AND a.branch_id = p.branch_id
LEFT JOIN shipping s ON a.sales_contact_id = s.sales_contact_id AND a.branch_id = s.branch_id
LEFT JOIN credit_note_sales cn ON a.sales_contact_id = cn.sales_contact_id AND a.branch_id = cn.branch_id
WHERE a.sales_contact_name IS NOT NULL
ORDER BY a.branch_id, a.sales_contact_name
"""

# ============================================================
# SQL: JV expense (สมุดรายวันทั่วไป name LIKE 'JV-%', state='posted')
# ============================================================
# คืน JV expense ต่อ branch — ใช้รวมเข้า total_expense ให้ตรงกับรายงานค่าคอมสาขา
SQL_JV = """
SELECT
    rb.id AS branch_id,
    rb.name AS branch_name,
    COALESCE(SUM(aml.debit), 0) AS jv_expense
FROM account_move am
JOIN account_move_line aml ON aml.move_id = am.id
LEFT JOIN res_branch rb ON am.branch_id = rb.id
WHERE am.state = 'posted'
    AND am.name LIKE 'JV-%%'
    AND am.date >= %(date_from)s
    AND am.date <= %(date_to)s
    AND aml.debit > 0
GROUP BY rb.id, rb.name
"""

# ============================================================
# SQL: Bankheaw (เทียบเท่า /api/commission/bankheaw — เอาเฉพาะ sort_order=0)
# ============================================================
SQL_BANKHEAW = """
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
    0 AS sort_order
FROM npd_sales_commission_report
WHERE EXTRACT(YEAR FROM report_date_from) = %(year)s
  AND EXTRACT(MONTH FROM report_date_from) = %(month)s
ORDER BY branch_id, report_type, salesperson_name
"""


class CrossDbCommissionQuery(models.AbstractModel):
    """Helper สำหรับ query ค่าคอมมิชชั่นจาก DB ปลายทางผ่าน psycopg2"""
    _name = 'cross_db.commission.query'
    _description = 'Cross-DB Commission Query (psycopg2)'

    # ============================================================
    # Configuration
    # ============================================================
    @api.model
    def get_db_list(self):
        """รายชื่อ DB ปลายทาง — ปรับผ่าน System Parameter ได้
        npd.commission.cross_db_list = "NPD_A,NPD_B,NPD_C"
        """
        param = self.env['ir.config_parameter'].sudo().get_param(
            'npd.commission.cross_db_list', default='')
        if param:
            return [d.strip() for d in param.split(',') if d.strip()]
        return [
            'NPD_Intertrading_New',
            'NPD_S_Group_New_V2',
            'NPD_Bangkok_New',
        ]

    @api.model
    def get_bankheaw_db(self):
        """DB ที่มีตาราง npd_sales_commission_report (bankheaw)"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'npd.commission.bankheaw_db', default='NPD_S_Group_New_V2')

    # ============================================================
    # Push salary snapshot จาก HRMS → DB ปลายทาง (ก่อนคิดค่าคอม)
    # ============================================================
    @api.model
    def push_salary_snapshot(self, month, year):
        """รีเฟรช salary snapshot ของ (month, year) ในทุก DB ปลายทาง
        - aggregate salary ต่อสาขาจาก payroll_salary บน HRMS (local) กรอง company
          ตาม param npd.salary_report.company ของ DB ปลายทางแต่ละตัว
        - เขียนทับ (DELETE + INSERT) ตาราง npd_salary_branch_report_line ของงวดนั้น
        ใช้ก่อนคิดค่าคอม เพื่อให้ salary expense ใน SQL_BRANCH สดเสมอ
        คืน dict {db_name: สถานะ} — ไม่ throw (กันไม่ให้ flow ทำเงินเดือนล้ม)
        """
        month = int(month)
        year = str(year)
        results = {}
        for db_name in self.get_db_list():
            try:
                # 1) อ่าน company param ของ DB ปลายทาง
                comp_rows, err = self._run_query(
                    db_name,
                    "SELECT value FROM ir_config_parameter WHERE key = %(k)s",
                    {'k': 'npd.salary_report.company'},
                )
                if err:
                    results[db_name] = 'param FAIL: %s' % err
                    continue
                company = ''
                if comp_rows and comp_rows[0].get('value'):
                    company = (comp_rows[0]['value'] or '').strip()

                # 2) aggregate salary บน HRMS (local) — กรอง company ถ้าตั้งไว้
                params = [month, year]
                company_clause = ''
                if company:
                    company_clause = 'AND es.company = %s'
                    params.append(company)
                self.env.cr.execute("""
                    SELECT COALESCE(b.name, '(ไม่ระบุสาขา)') AS branch_name,
                           COUNT(DISTINCT ps.employee_id) AS employee_count,
                           COALESCE(SUM(
                               COALESCE(ps.total_gross, 0)
                               - COALESCE(ps.income_commission, 0)
                               - COALESCE(ps.income_commission_sale, 0)
                           ), 0) AS total_income
                    FROM payroll_salary ps
                    LEFT JOIN employee_salary es ON es.id = ps.employee_id
                    LEFT JOIN hr_branch_custom b ON b.id = ps.branch_id
                    WHERE ps.month = %s
                      AND ps.year = %s
                      AND COALESCE(ps.active, TRUE) = TRUE
                      {company_clause}
                    GROUP BY b.id, b.name
                """.format(company_clause=company_clause), params)
                rows = self.env.cr.dictfetchall()

                # 3) เขียนทับ snapshot ใน DB ปลายทาง (DELETE + INSERT) ใน transaction เดียว
                conn = self._connect(db_name)
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM npd_salary_branch_report_line "
                            "WHERE month = %s AND year = %s",
                            (month, year),
                        )
                        for r in rows:
                            cur.execute("""
                                INSERT INTO npd_salary_branch_report_line
                                    (month, year, branch_name, employee_count, total_income,
                                     last_refresh, create_date, write_date)
                                VALUES (%s, %s, %s, %s, %s, now(), now(), now())
                            """, (
                                month, year,
                                r['branch_name'],
                                int(r['employee_count'] or 0),
                                float(r['total_income'] or 0.0),
                            ))
                    conn.commit()
                    results[db_name] = 'OK (%d สาขา)' % len(rows)
                except psycopg2.Error as e:
                    conn.rollback()
                    results[db_name] = 'write FAIL: %s' % str(e).strip()[:150]
                    _logger.warning("[PUSH-SNAPSHOT][%s] write fail: %s", db_name, e)
                finally:
                    conn.close()
            except Exception as e:
                results[db_name] = 'ERROR: %s' % str(e)[:150]
                _logger.exception("[PUSH-SNAPSHOT][%s] %s", db_name, e)
        _logger.info("[PUSH-SNAPSHOT] month=%s year=%s → %s", month, year, results)
        return results

    # ============================================================
    # Connection
    # ============================================================
    @api.model
    def _connect(self, db_name):
        """เปิด connection ไป DB ปลายทาง — ใช้ connection params ของ Odoo instance นี้"""
        conn_params = {
            'dbname': db_name,
            'user': config.get('db_user') or 'odoo',
            'password': config.get('db_password') or '',
            'host': config.get('db_host') or 'localhost',
            'port': config.get('db_port') or 5432,
        }
        conn_params = {k: v for k, v in conn_params.items() if v not in (None, '', False)}
        return psycopg2.connect(**conn_params)

    @api.model
    def _run_query(self, db_name, sql, params):
        """รัน SQL บน DB ปลายทาง คืน list[dict] — ดักทุก error ไม่ให้ล้ม flow ผู้เรียก
        คืน (rows, error_msg) — error_msg = '' ถ้าสำเร็จ
        """
        try:
            conn = self._connect(db_name)
        except psycopg2.Error as e:
            msg = "Connect FAIL: %s" % str(e).strip()
            _logger.warning("[CROSS-DB][%s] %s", db_name, msg)
            return [], msg

        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = [dict(r) for r in cur.fetchall()]
                return rows, ''
        except psycopg2.Error as e:
            msg = "Query FAIL: %s" % str(e).strip()[:200]
            _logger.warning("[CROSS-DB][%s] %s", db_name, msg)
            return [], msg
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ============================================================
    # Public Queries — คืน shape เดียวกับ API เดิม
    # ============================================================
    @api.model
    def query_branch(self, db_name, date_from, date_to):
        """เทียบเท่า POST /api/commission/branch
        คืน list[dict]: branch_id, branch_name, rental_amount, payment_received,
                        outstanding_debt, total_expense, net_rental
        """
        params = {'date_from': str(date_from), 'date_to': str(date_to)}
        rows, err = self._run_query(db_name, SQL_BRANCH, params)
        # cast Decimal → float
        for r in rows:
            for k in ('rental_amount', 'payment_received', 'outstanding_debt',
                      'total_expense', 'net_rental'):
                if k in r and r[k] is not None:
                    r[k] = float(r[k])
        return rows, err

    @api.model
    def query_sales(self, db_name, date_from, date_to):
        """เทียบเท่า POST /api/commission/sales
        คืน list[dict]: sales_contact_id, sales_contact_name, employee_code,
                        branch_id, branch_name, rental_amount, payment_received,
                        outstanding_debt, shipping_cost, net_rental
        """
        params = {'date_from': str(date_from), 'date_to': str(date_to)}
        rows, err = self._run_query(db_name, SQL_SALES, params)
        for r in rows:
            for k in ('rental_amount', 'payment_received', 'outstanding_debt',
                      'shipping_cost', 'net_rental'):
                if k in r and r[k] is not None:
                    r[k] = float(r[k])
        return rows, err

    @api.model
    def query_jv(self, db_name, date_from, date_to):
        """JV expense per branch (สมุดรายวันทั่วไป) — เทียบเท่ากับที่ _compute_branch_data ใช้
        คืน list[dict]: branch_id, branch_name, jv_expense (SUM ของ debit ทุกบรรทัด, state='posted')
        """
        params = {'date_from': str(date_from), 'date_to': str(date_to)}
        rows, err = self._run_query(db_name, SQL_JV, params)
        for r in rows:
            if 'jv_expense' in r and r['jv_expense'] is not None:
                r['jv_expense'] = float(r['jv_expense'])
        return rows, err

    @api.model
    def query_bankheaw(self, db_name, month, year):
        """เทียบเท่า POST /api/commission/bankheaw (เอาเฉพาะ sort_order=0)
        คืน list[dict]: period, type ('สาขา'/'เซลล์'), branch_name, employee_code,
                        salesperson_name, total_rent_revenue, total_paid,
                        net_outstanding, net_total, sort_order=0
        """
        params = {'month': int(month), 'year': int(year)}
        rows, err = self._run_query(db_name, SQL_BANKHEAW, params)
        for r in rows:
            for k in ('initial_rent', 'discount', 'rent_difference', 'total_rent_revenue',
                      'outstanding_bill_count', 'total_outstanding', 'total_paid',
                      'net_outstanding', 'old_debt_paid', 'net_total'):
                if k in r and r[k] is not None:
                    r[k] = float(r[k])
        return rows, err
