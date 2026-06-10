-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║ รายงานค่าคอมมิชชั่นสาขา (Branch Commission Report)                       ║
-- ║                                                                          ║
-- ║ Match logic เดียวกับ npd.commission.report (_compute_branch_data):       ║
-- ║   - rental: เฉพาะ "สมุดรายวันเช่า(สาขา)" (ไม่รวมสมุดค่าปรับ)              ║
-- ║   - credit_note: หักออกจาก rental (ไม่ filter payment_state)             ║
-- ║   - outstanding: as-of-date จาก account_partial_reconcile (as of date_to)║
-- ║   - vendor: amount_total − amount_residual                              ║
-- ║   - advance_clear: tax-aware (ภาษีซื้อรวม/ไม่รวม Vat 7%)                  ║
-- ║   - voucher: avl.price_subtotal โดยกรองด้วย payment_date                ║
-- ║   - JV: account_move name LIKE 'JV-%', state='posted', SUM(debit)        ║
-- ║   - salary: จาก npd_salary_branch_report_line ถ้า expense อื่น > 0       ║
-- ║                                                                          ║
-- ║ Output: detail per (เดือน, สาขา) + รวมเดือน + ★ รวมทั้งปี                 ║
-- ║                                                                          ║
-- ║ ⚙️ เปลี่ยน min_year ใน CTE params                                        ║
-- ║   default = 2026 → จาก 1/1/2026 เป็นต้นไป (ขึ้นปี 2027 เห็นเองอัตโนมัติ)    ║
-- ║   ตั้ง EXTRACT(YEAR FROM CURRENT_DATE)::int → ปีปัจจุบันเสมอ              ║
-- ║   ตั้ง 1900 → ทุกปี                                                       ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

WITH params AS (
    SELECT 2026::int AS min_year   -- 🔧 เริ่มจาก 1/1/2026 เป็นต้นไป
),

-- 1) Detect (year, month) ทั้งหมดที่มีข้อมูล (auto add เดือนใหม่)
periods AS (
    SELECT DISTINCT
        EXTRACT(YEAR FROM am.invoice_date)::int AS year,
        EXTRACT(MONTH FROM am.invoice_date)::int AS month
    FROM account_move am
    JOIN account_journal aj ON am.journal_id = aj.id
    CROSS JOIN params p
    WHERE am.state = 'posted'
      AND am.invoice_date IS NOT NULL
      AND aj.name IN (
          'สมุดรายวันเช่า(สาขา)', 'สมุดรายวันค่าปรับหาย', 'สมุดรายวันค่าปรับชำรุด',
          'สมุดรายวันลดหนี้ขาย', 'สมุดรายวันรับชำระ',
          'สมุดรายวันรับชำระค่าปรับหาย', 'สมุดรายวันรับชำระค่าปรับชำรุด'
      )
      AND EXTRACT(YEAR FROM am.invoice_date)::int >= p.min_year
),
period_dates AS (
    SELECT year, month,
        MAKE_DATE(year, month, 1) AS date_from,
        (MAKE_DATE(year, month, 1) + INTERVAL '1 month' - INTERVAL '1 day')::date AS date_to
    FROM periods
),

-- 2) ยอดเช่า — เฉพาะ "สมุดรายวันเช่า(สาขา)"
rental AS (
    SELECT
        EXTRACT(YEAR FROM am.invoice_date)::int AS year,
        EXTRACT(MONTH FROM am.invoice_date)::int AS month,
        rb.id AS branch_id,
        SUM(am.amount_untaxed) AS rental_amount
    FROM account_move am
    JOIN account_journal aj ON am.journal_id = aj.id
    JOIN res_branch rb ON am.branch_id = rb.id
    CROSS JOIN params p
    WHERE aj.name = 'สมุดรายวันเช่า(สาขา)'
      AND am.state = 'posted' AND am.move_type = 'out_invoice'
      AND am.contact_type = 'branch'
      AND EXTRACT(YEAR FROM am.invoice_date)::int >= p.min_year
    GROUP BY 1, 2, 3
),

-- 3) ใบลดหนี้ขาย (หักออกจาก rental — ไม่ filter payment_state)
credit_note AS (
    SELECT
        EXTRACT(YEAR FROM am.invoice_date)::int AS year,
        EXTRACT(MONTH FROM am.invoice_date)::int AS month,
        rb.id AS branch_id,
        SUM(am.amount_untaxed) AS cn_amount
    FROM account_move am
    JOIN account_journal aj ON am.journal_id = aj.id
    JOIN res_branch rb ON am.branch_id = rb.id
    CROSS JOIN params p
    WHERE aj.name = 'สมุดรายวันลดหนี้ขาย'
      AND am.state = 'posted' AND am.move_type = 'out_refund'
      AND am.contact_type = 'branch'
      AND EXTRACT(YEAR FROM am.invoice_date)::int >= p.min_year
    GROUP BY 1, 2, 3
),

-- 4) หนี้ค้างชำระ (as-of-date ณ สิ้นเดือนของแต่ละ period)
outstanding AS (
    SELECT pd.year, pd.month, rl.branch_id,
        SUM(GREATEST(0, rl.balance - COALESCE(p.paid_amount, 0))) / 1.07 AS outstanding_debt
    FROM period_dates pd
    JOIN LATERAL (
        SELECT am.id AS move_id, am.branch_id, aml.id AS line_id,
               (COALESCE(aml.debit, 0) - COALESCE(aml.credit, 0)) AS balance
        FROM account_move am
        JOIN account_journal aj ON am.journal_id = aj.id
        JOIN account_move_line aml ON aml.move_id = am.id
        JOIN account_account aa ON aa.id = aml.account_id
        WHERE aj.name IN ('สมุดรายวันเช่า(สาขา)', 'สมุดรายวันค่าปรับหาย', 'สมุดรายวันค่าปรับชำรุด')
          AND am.state = 'posted' AND am.move_type = 'out_invoice'
          AND am.contact_type = 'branch'
          AND am.invoice_date BETWEEN pd.date_from AND pd.date_to
          AND aa.internal_type = 'receivable'
    ) rl ON TRUE
    LEFT JOIN LATERAL (
        SELECT COALESCE(SUM(amount), 0) AS paid_amount FROM (
            SELECT apr.amount FROM account_partial_reconcile apr
            JOIN account_move_line cml ON cml.id = apr.credit_move_id
            JOIN account_move cm ON cm.id = cml.move_id
            WHERE apr.debit_move_id = rl.line_id AND cm.date <= pd.date_to
            UNION ALL
            SELECT apr.amount FROM account_partial_reconcile apr
            JOIN account_move_line dml ON dml.id = apr.debit_move_id
            JOIN account_move dm ON dm.id = dml.move_id
            WHERE apr.credit_move_id = rl.line_id AND dm.date <= pd.date_to
        ) sub
    ) p ON TRUE
    GROUP BY pd.year, pd.month, rl.branch_id
),

-- 4b) ✅ หนี้ค้างจาก "ใบค่าปรับ" (สินค้าหาย/ชำรุด) — อยู่นอก 3 สมุดเช่า/ปรับ
--      ใน ORM: filter reason_code_id ใน scrap.reason.code (name = สินค้าหาย, สินค้าชำรุด)
--                journal_id NOT IN (สมุดรายวันเช่า/ปรับหาย/ปรับชำรุด)
penalty_outstanding AS (
    SELECT pd.year, pd.month, rl.branch_id,
        SUM(GREATEST(0, rl.balance - COALESCE(p.paid_amount, 0))) / 1.07 AS penalty_amount
    FROM period_dates pd
    JOIN LATERAL (
        SELECT am.id AS move_id, am.branch_id, aml.id AS line_id,
               (COALESCE(aml.debit, 0) - COALESCE(aml.credit, 0)) AS balance
        FROM account_move am
        JOIN account_journal aj ON am.journal_id = aj.id
        JOIN account_move_line aml ON aml.move_id = am.id
        JOIN account_account aa ON aa.id = aml.account_id
        JOIN scrap_reason_code src ON src.id = am.reason_code_id
        WHERE aj.name NOT IN ('สมุดรายวันเช่า(สาขา)', 'สมุดรายวันค่าปรับหาย', 'สมุดรายวันค่าปรับชำรุด')
          AND am.state = 'posted' AND am.move_type = 'out_invoice'
          AND am.contact_type = 'branch'
          AND src.name IN ('สินค้าหาย', 'สินค้าชำรุด')
          AND am.invoice_date BETWEEN pd.date_from AND pd.date_to
          AND aa.internal_type = 'receivable'
    ) rl ON TRUE
    LEFT JOIN LATERAL (
        SELECT COALESCE(SUM(amount), 0) AS paid_amount FROM (
            SELECT apr.amount FROM account_partial_reconcile apr
            JOIN account_move_line cml ON cml.id = apr.credit_move_id
            JOIN account_move cm ON cm.id = cml.move_id
            WHERE apr.debit_move_id = rl.line_id AND cm.date <= pd.date_to
            UNION ALL
            SELECT apr.amount FROM account_partial_reconcile apr
            JOIN account_move_line dml ON dml.id = apr.debit_move_id
            JOIN account_move dm ON dm.id = dml.move_id
            WHERE apr.credit_move_id = rl.line_id AND dm.date <= pd.date_to
        ) sub
    ) p ON TRUE
    GROUP BY pd.year, pd.month, rl.branch_id
),

-- 5) รับชำระหนี้ (cross-month — payment.date คนละเดือนกับ invoice.invoice_date)
payment AS (
    SELECT sub.year, sub.month, sub.branch_id,
        SUM(sub.payment_amount) AS payment_received
    FROM (
        SELECT DISTINCT
            ap.id AS payment_id,
            EXTRACT(YEAR FROM am.date)::int AS year,
            EXTRACT(MONTH FROM am.date)::int AS month,
            rb.id AS branch_id,
            ap.amount / 1.07 AS payment_amount
        FROM account_payment ap
        JOIN account_move am ON ap.move_id = am.id
        JOIN account_journal aj ON am.journal_id = aj.id
        JOIN res_branch rb ON ap.branch_id = rb.id
        JOIN account_move_line aml ON aml.payment_id = ap.id
        JOIN account_partial_reconcile apr
            ON apr.credit_move_id = aml.id OR apr.debit_move_id = aml.id
        JOIN account_move_line aml2
            ON (apr.debit_move_id = aml2.id OR apr.credit_move_id = aml2.id)
            AND aml2.id != aml.id
        JOIN account_move inv ON aml2.move_id = inv.id AND inv.move_type = 'out_invoice'
        CROSS JOIN params p
        WHERE aj.name IN ('สมุดรายวันรับชำระ', 'สมุดรายวันรับชำระค่าปรับหาย', 'สมุดรายวันรับชำระค่าปรับชำรุด')
          AND am.state = 'posted'
          AND inv.invoice_date IS NOT NULL AND inv.contact_type = 'branch'
          AND (EXTRACT(MONTH FROM am.date) != EXTRACT(MONTH FROM inv.invoice_date)
               OR EXTRACT(YEAR FROM am.date) != EXTRACT(YEAR FROM inv.invoice_date))
          AND am.date > inv.invoice_date
          AND EXTRACT(YEAR FROM am.date)::int >= p.min_year
    ) sub
    GROUP BY sub.year, sub.month, sub.branch_id
),

-- 6a) Vendor Bills expense (amount_total − amount_residual)
vendor_expense AS (
    SELECT
        EXTRACT(YEAR FROM bill.invoice_date)::int AS year,
        EXTRACT(MONTH FROM bill.invoice_date)::int AS month,
        rb.id AS branch_id,
        COALESCE(SUM(COALESCE(bill.amount_total, 0) - COALESCE(bill.amount_residual, 0)), 0) AS vendor_amount
    FROM account_move bill
    JOIN res_branch rb ON bill.branch_id = rb.id
    CROSS JOIN params p
    WHERE bill.state = 'posted'
      AND bill.move_type IN ('in_invoice', 'in_refund')
      AND bill.invoice_date IS NOT NULL
      AND EXTRACT(YEAR FROM bill.invoice_date)::int >= p.min_year
    GROUP BY 1, 2, 3
),

-- 6b) Advance Clear expense (tax-aware)
advance_expense AS (
    SELECT
        EXTRACT(YEAR FROM aac.doc_date)::int AS year,
        EXTRACT(MONTH FROM aac.doc_date)::int AS month,
        aaa.branch_id AS branch_id,
        SUM(
            CASE
                WHEN EXISTS (SELECT 1 FROM account_tax_advance_clear_line_rel rel
                    JOIN account_tax at ON rel.account_tax_id = at.id
                    WHERE rel.advance_clear_line_id = acl.id
                    AND at.name LIKE '%ภาษีซื้อรวม Vat 7%')
                THEN acl.price_unit
                WHEN EXISTS (SELECT 1 FROM account_tax_advance_clear_line_rel rel
                    JOIN account_tax at ON rel.account_tax_id = at.id
                    WHERE rel.advance_clear_line_id = acl.id
                    AND at.name LIKE '%ภาษีซื้อไม่รวม Vat 7%')
                THEN acl.price_unit * 1.07
                WHEN NOT EXISTS (SELECT 1 FROM account_tax_advance_clear_line_rel rel
                    WHERE rel.advance_clear_line_id = acl.id)
                THEN acl.price_subtotal
                ELSE 0
            END
        ) AS advance_amount
    FROM account_advance_clear aac
    JOIN advance_clear_line acl ON acl.advance_clear_id = aac.id
    JOIN account_analytic_account aaa ON acl.account_analytic_id = aaa.id
    CROSS JOIN params p
    WHERE aac.state = 'post'
      AND aaa.branch_id IS NOT NULL
      AND aac.doc_date IS NOT NULL
      AND EXTRACT(YEAR FROM aac.doc_date)::int >= p.min_year
    GROUP BY 1, 2, 3
),

-- 6c) Voucher expense (ดึงจาก account.voucher หัวเอกสาร: branch_id + amount รวม VAT)
voucher_expense AS (
    SELECT
        EXTRACT(YEAR FROM av.date)::int AS year,
        EXTRACT(MONTH FROM av.date)::int AS month,
        av.branch_id AS branch_id,
        SUM(av.amount) AS voucher_amount
    FROM account_voucher av
    CROSS JOIN params p
    WHERE av.state IN ('posted', 'transferred')
      AND av.branch_id IS NOT NULL
      AND av.date IS NOT NULL
      AND EXTRACT(YEAR FROM av.date)::int >= p.min_year
    GROUP BY 1, 2, 3
),

-- 6d) JV expense (account_move name LIKE 'JV-%', state=posted)
jv_expense AS (
    SELECT
        EXTRACT(YEAR FROM am.date)::int AS year,
        EXTRACT(MONTH FROM am.date)::int AS month,
        rb.id AS branch_id,
        COALESCE(SUM(aml.debit), 0) AS jv_amount
    FROM account_move am
    JOIN account_move_line aml ON aml.move_id = am.id
    JOIN res_branch rb ON am.branch_id = rb.id
    CROSS JOIN params p
    WHERE am.state = 'posted'
      AND am.name LIKE 'JV-%'
      AND am.date IS NOT NULL
      AND aml.debit > 0
      AND EXTRACT(YEAR FROM am.date)::int >= p.min_year
    GROUP BY 1, 2, 3
),

-- 6e) Salary expense (จาก snapshot npd_salary_branch_report_line, match by branch_name)
salary_expense AS (
    SELECT s.year::int AS year, s.month::int AS month,
        rb.id AS branch_id,
        COALESCE(SUM(s.total_income), 0) AS salary_amount
    FROM npd_salary_branch_report_line s
    JOIN res_branch rb ON rb.name = s.branch_name
    CROSS JOIN params p
    WHERE s.year::int >= p.min_year
    GROUP BY 1, 2, 3
),

-- 7) รวม branch ทั้งหมดที่ปรากฏใน CTE ใดก็ตาม
all_keys AS (
    SELECT DISTINCT year, month, branch_id FROM (
        SELECT year, month, branch_id FROM rental
        UNION ALL SELECT year, month, branch_id FROM credit_note
        UNION ALL SELECT year, month, branch_id FROM outstanding
        UNION ALL SELECT year, month, branch_id FROM penalty_outstanding
        UNION ALL SELECT year, month, branch_id FROM payment
        UNION ALL SELECT year, month, branch_id FROM vendor_expense
        UNION ALL SELECT year, month, branch_id FROM advance_expense
        UNION ALL SELECT year, month, branch_id FROM voucher_expense
        UNION ALL SELECT year, month, branch_id FROM jv_expense
        UNION ALL SELECT year, month, branch_id FROM salary_expense
    ) sub WHERE branch_id IS NOT NULL
),

-- 8) Combine + คำนวณ total_expense + net (salary บวกเฉพาะถ้า other > 0)
final_calc AS (
    SELECT
        ak.year, ak.month, ak.branch_id, rb.name AS branch_name,
        (COALESCE(r.rental_amount, 0) - COALESCE(cn.cn_amount, 0)) AS rental,
        COALESCE(pmt.payment_received, 0) AS payment,
        (COALESCE(o.outstanding_debt, 0) + COALESCE(po.penalty_amount, 0)) AS outstanding,
        (
            COALESCE(ve.vendor_amount, 0) + COALESCE(ae.advance_amount, 0)
            + COALESCE(vo.voucher_amount, 0) + COALESCE(jv.jv_amount, 0)
            + CASE
                WHEN (COALESCE(ve.vendor_amount, 0) + COALESCE(ae.advance_amount, 0)
                      + COALESCE(vo.voucher_amount, 0) + COALESCE(jv.jv_amount, 0)) > 0
                THEN COALESCE(sal.salary_amount, 0)
                ELSE 0
              END
        ) AS total_expense
    FROM all_keys ak
    JOIN res_branch rb ON rb.id = ak.branch_id
    LEFT JOIN rental r ON r.year = ak.year AND r.month = ak.month AND r.branch_id = ak.branch_id
    LEFT JOIN credit_note cn ON cn.year = ak.year AND cn.month = ak.month AND cn.branch_id = ak.branch_id
    LEFT JOIN payment pmt ON pmt.year = ak.year AND pmt.month = ak.month AND pmt.branch_id = ak.branch_id
    LEFT JOIN outstanding o ON o.year = ak.year AND o.month = ak.month AND o.branch_id = ak.branch_id
    LEFT JOIN penalty_outstanding po ON po.year = ak.year AND po.month = ak.month AND po.branch_id = ak.branch_id
    LEFT JOIN vendor_expense ve ON ve.year = ak.year AND ve.month = ak.month AND ve.branch_id = ak.branch_id
    LEFT JOIN advance_expense ae ON ae.year = ak.year AND ae.month = ak.month AND ae.branch_id = ak.branch_id
    LEFT JOIN voucher_expense vo ON vo.year = ak.year AND vo.month = ak.month AND vo.branch_id = ak.branch_id
    LEFT JOIN jv_expense jv ON jv.year = ak.year AND jv.month = ak.month AND jv.branch_id = ak.branch_id
    LEFT JOIN salary_expense sal ON sal.year = ak.year AND sal.month = ak.month AND sal.branch_id = ak.branch_id
),

-- 9) Detail rows
detail_rows AS (
    SELECT
        year::text || '-' || LPAD(month::text, 2, '0') AS period_label,
        branch_id::text AS branch_code,
        branch_name AS branch_label,
        ROUND(rental::numeric, 2) AS rental_amount,
        ROUND(payment::numeric, 2) AS payment_received,
        ROUND(outstanding::numeric, 2) AS outstanding_debt,
        ROUND(total_expense::numeric, 2) AS total_expense,
        ROUND((rental + payment - outstanding - total_expense)::numeric, 2) AS net_rental,
        year AS sort_year, month AS sort_month, 0 AS sort_order, branch_id AS sort_branch_id
    FROM final_calc
),

-- 10) Subtotal per month
subtotal_rows AS (
    SELECT
        year::text || '-' || LPAD(month::text, 2, '0') AS period_label,
        NULL::text AS branch_code,
        'รวมเดือน ' || year::text || '-' || LPAD(month::text, 2, '0') AS branch_label,
        ROUND(SUM(rental)::numeric, 2) AS rental_amount,
        ROUND(SUM(payment)::numeric, 2) AS payment_received,
        ROUND(SUM(outstanding)::numeric, 2) AS outstanding_debt,
        ROUND(SUM(total_expense)::numeric, 2) AS total_expense,
        ROUND(SUM(rental + payment - outstanding - total_expense)::numeric, 2) AS net_rental,
        year AS sort_year, month AS sort_month, 1 AS sort_order, NULL::int AS sort_branch_id
    FROM final_calc GROUP BY year, month
),

-- 11) Grand total per year
grand_total_rows AS (
    SELECT
        year::text || '-99' AS period_label,
        NULL::text AS branch_code,
        '★ รวมทั้งปี ' || year::text AS branch_label,
        ROUND(SUM(rental)::numeric, 2) AS rental_amount,
        ROUND(SUM(payment)::numeric, 2) AS payment_received,
        ROUND(SUM(outstanding)::numeric, 2) AS outstanding_debt,
        ROUND(SUM(total_expense)::numeric, 2) AS total_expense,
        ROUND(SUM(rental + payment - outstanding - total_expense)::numeric, 2) AS net_rental,
        year AS sort_year, 99 AS sort_month, 2 AS sort_order, NULL::int AS sort_branch_id
    FROM final_calc GROUP BY year
)

SELECT
    period_label     AS "เดือน",
    branch_code      AS "รหัสสาขา",
    branch_label     AS "สาขา",
    rental_amount    AS "ยอดเช่า",
    payment_received AS "รับชำระหนี้",
    outstanding_debt AS "หนี้ค้างชำระ",
    total_expense    AS "รายจ่ายรวม",
    net_rental       AS "ยอดเช่าสุทธิ"
FROM (
    SELECT * FROM detail_rows
    UNION ALL SELECT * FROM subtotal_rows
    UNION ALL SELECT * FROM grand_total_rows
) all_rows
ORDER BY sort_year ASC, sort_month ASC, sort_order ASC, sort_branch_id ASC NULLS LAST;
