-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║ รายงานค่าคอมมิชชั่น Sales                                                ║
-- ║                                                                          ║
-- ║ Match logic เดียวกับ npd.commission.report.sales (_compute_sales_data):  ║
-- ║   - rental: "สมุดรายวันเช่า(สาขา)" contact_type='sale' sales_contact_id  ║
-- ║   - credit_note: หักออกจาก rental                                        ║
-- ║   - outstanding: as-of-date จาก account_partial_reconcile                ║
-- ║   - payment: cross-month จาก 'สมุดรายวันรับชำระ'                          ║
-- ║   - shipping: จาก account_voucher_line ที่มี sales_contact_id            ║
-- ║                                                                          ║
-- ║ Output: detail per (เดือน, สาขา, Sales) + รวมเดือน + ★ รวมทั้งปี          ║
-- ║                                                                          ║
-- ║ ⚙️ default min_year = 2026 (1/1/2026 เป็นต้นไป, auto add ปีถัดไป)         ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

WITH params AS (
    SELECT 2026::int AS min_year   -- 🔧 เริ่มจาก 1/1/2026 เป็นต้นไป
),

-- 🔧 รายชื่อ "Sales สำนักงานใหญ่" (employee_code) — กรณีพิเศษ: ยอดเช่านับเฉพาะบิลแรก
--    (SO deposit_ref ว่าง). อัปเดตรายชื่อจาก query บน DB HRMS:
--      SELECT es.employee_code FROM commission_sale_headoffice ho
--      JOIN employee_salary es ON es.id = ho.employee_id;
headoffice AS (
    SELECT unnest(ARRAY['1094','1285']::text[]) AS employee_code
),

-- 1) Detect (year, month) ที่มีข้อมูล
periods AS (
    SELECT DISTINCT
        EXTRACT(YEAR FROM am.invoice_date)::int AS year,
        EXTRACT(MONTH FROM am.invoice_date)::int AS month
    FROM account_move am
    JOIN account_journal aj ON am.journal_id = aj.id
    CROSS JOIN params p
    WHERE am.state = 'posted' AND am.invoice_date IS NOT NULL
      AND am.contact_type = 'sale'
      AND am.sales_contact_id IS NOT NULL
      AND aj.name IN ('สมุดรายวันเช่า(สาขา)', 'สมุดรายวันลดหนี้ขาย', 'สมุดรายวันรับชำระ')
      AND EXTRACT(YEAR FROM am.invoice_date)::int >= p.min_year
),
period_dates AS (
    SELECT year, month,
        MAKE_DATE(year, month, 1) AS date_from,
        (MAKE_DATE(year, month, 1) + INTERVAL '1 month' - INTERVAL '1 day')::date AS date_to
    FROM periods
),

-- 2) ยอดเช่า (เฉพาะ "สมุดรายวันเช่า(สาขา)" contact_type='sale')
rental AS (
    SELECT
        EXTRACT(YEAR FROM am.invoice_date)::int AS year,
        EXTRACT(MONTH FROM am.invoice_date)::int AS month,
        am.sales_contact_id,
        am.branch_id,
        SUM(am.amount_untaxed) AS rental_amount
    FROM account_move am
    JOIN account_journal aj ON am.journal_id = aj.id
    LEFT JOIN res_users ru ON am.sales_contact_id = ru.id
    CROSS JOIN params p
    WHERE aj.name = 'สมุดรายวันเช่า(สาขา)'
      AND am.state = 'posted' AND am.move_type = 'out_invoice'
      AND am.contact_type = 'sale'
      AND am.sales_contact_id IS NOT NULL
      AND EXTRACT(YEAR FROM am.invoice_date)::int >= p.min_year
      -- ✅ Sales สนญ.: นับเฉพาะบิลแรก (SO deposit_ref ว่าง) / Sales ปกติ → นับทุกบิล
      AND (
          ru.employee_code IS NULL
          OR ru.employee_code NOT IN (SELECT employee_code FROM headoffice)
          OR NOT EXISTS (
              SELECT 1 FROM sale_order so
              WHERE so.name = am.invoice_origin
                AND NULLIF(BTRIM(so.deposit_ref), '') IS NOT NULL
          )
      )
    GROUP BY 1, 2, 3, 4
),

-- 3) ใบลดหนี้ขาย (หักจาก rental)
credit_note AS (
    SELECT
        EXTRACT(YEAR FROM am.invoice_date)::int AS year,
        EXTRACT(MONTH FROM am.invoice_date)::int AS month,
        am.sales_contact_id,
        am.branch_id,
        SUM(am.amount_untaxed) AS cn_amount
    FROM account_move am
    JOIN account_journal aj ON am.journal_id = aj.id
    CROSS JOIN params p
    WHERE aj.name = 'สมุดรายวันลดหนี้ขาย'
      AND am.state = 'posted' AND am.move_type = 'out_refund'
      AND am.contact_type = 'sale'
      AND am.sales_contact_id IS NOT NULL
      AND EXTRACT(YEAR FROM am.invoice_date)::int >= p.min_year
    GROUP BY 1, 2, 3, 4
),

-- 4) หนี้ค้างชำระ (as-of-date ณ สิ้นเดือน)
outstanding AS (
    SELECT pd.year, pd.month, rl.sales_contact_id, rl.branch_id,
        SUM(GREATEST(0, rl.balance - COALESCE(p.paid_amount, 0))) / 1.07 AS outstanding_debt
    FROM period_dates pd
    JOIN LATERAL (
        SELECT am.id AS move_id, am.sales_contact_id, am.branch_id, aml.id AS line_id,
               (COALESCE(aml.debit, 0) - COALESCE(aml.credit, 0)) AS balance
        FROM account_move am
        JOIN account_journal aj ON am.journal_id = aj.id
        JOIN account_move_line aml ON aml.move_id = am.id
        JOIN account_account aa ON aa.id = aml.account_id
        WHERE aj.name IN ('สมุดรายวันเช่า(สาขา)', 'สมุดรายวันค่าปรับหาย', 'สมุดรายวันค่าปรับชำรุด')
          AND am.state = 'posted' AND am.move_type = 'out_invoice'
          AND am.contact_type = 'sale'
          AND am.sales_contact_id IS NOT NULL
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
    GROUP BY pd.year, pd.month, rl.sales_contact_id, rl.branch_id
),

-- 4b) ✅ หนี้ค้างจาก "ใบค่าปรับ" (สินค้าหาย/ชำรุด) — อยู่นอกสมุดเช่า, as-of-date
--      ใน ORM: filter reason_code_id ใน scrap.reason.code (name = สินค้าหาย, สินค้าชำรุด)
--                journal_id != สมุดรายวันเช่า(สาขา)
penalty_outstanding AS (
    SELECT pd.year, pd.month, rl.sales_contact_id, rl.branch_id,
        SUM(GREATEST(0, rl.balance - COALESCE(p.paid_amount, 0))) / 1.07 AS penalty_amount
    FROM period_dates pd
    JOIN LATERAL (
        SELECT am.id AS move_id, am.sales_contact_id, am.branch_id, aml.id AS line_id,
               (COALESCE(aml.debit, 0) - COALESCE(aml.credit, 0)) AS balance
        FROM account_move am
        JOIN account_journal aj ON am.journal_id = aj.id
        JOIN account_move_line aml ON aml.move_id = am.id
        JOIN account_account aa ON aa.id = aml.account_id
        JOIN scrap_reason_code src ON src.id = am.reason_code_id
        WHERE aj.name NOT IN ('สมุดรายวันเช่า(สาขา)', 'สมุดรายวันค่าปรับหาย', 'สมุดรายวันค่าปรับชำรุด')
          AND am.state = 'posted' AND am.move_type = 'out_invoice'
          AND am.contact_type = 'sale'
          AND am.sales_contact_id IS NOT NULL
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
    GROUP BY pd.year, pd.month, rl.sales_contact_id, rl.branch_id
),

-- 5) รับชำระหนี้ (cross-month จาก 'สมุดรายวันรับชำระ')
payment AS (
    SELECT sub.year, sub.month, sub.sales_contact_id, sub.branch_id,
        SUM(sub.payment_amount) AS payment_received
    FROM (
        SELECT DISTINCT
            ap.id AS payment_id,
            EXTRACT(YEAR FROM am.date)::int AS year,
            EXTRACT(MONTH FROM am.date)::int AS month,
            inv.sales_contact_id,
            inv.branch_id,
            -- ค่าปรับชำรุด ไม่ถอด VAT (ใช้ยอดเต็ม) / สมุดอื่นถอด VAT 7%
            CASE WHEN aj.name = 'สมุดรายวันรับชำระค่าปรับชำรุด' THEN ap.amount ELSE ap.amount / 1.07 END AS payment_amount
        FROM account_payment ap
        JOIN account_move am ON ap.move_id = am.id
        JOIN account_journal aj ON am.journal_id = aj.id
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
          AND inv.invoice_date IS NOT NULL
          AND inv.contact_type = 'sale'
          AND inv.sales_contact_id IS NOT NULL
          AND (EXTRACT(MONTH FROM am.date) != EXTRACT(MONTH FROM inv.invoice_date)
               OR EXTRACT(YEAR FROM am.date) != EXTRACT(YEAR FROM inv.invoice_date))
          AND am.date > inv.invoice_date
          AND EXTRACT(YEAR FROM am.date)::int >= p.min_year
    ) sub
    GROUP BY sub.year, sub.month, sub.sales_contact_id, sub.branch_id
),

-- 6) ค่าขนส่ง (จาก account_voucher_line ที่มี sales_contact_id)
shipping AS (
    SELECT
        EXTRACT(YEAR FROM av.date)::int AS year,
        EXTRACT(MONTH FROM av.date)::int AS month,
        avl.sales_contact_id,
        av.branch_id,
        SUM(avl.price_subtotal) AS shipping_cost
    FROM account_voucher av
    JOIN account_voucher_line avl ON avl.voucher_id = av.id
    CROSS JOIN params p
    WHERE av.state IN ('posted', 'transferred')
      AND avl.sales_contact_id IS NOT NULL
      AND av.date IS NOT NULL
      AND EXTRACT(YEAR FROM av.date)::int >= p.min_year
    GROUP BY 1, 2, 3, 4
),

-- 7) รวมทุก (year, month, sales_contact, branch) ที่ปรากฏ
all_keys AS (
    SELECT DISTINCT year, month, sales_contact_id, branch_id FROM (
        SELECT year, month, sales_contact_id, branch_id FROM rental
        UNION ALL SELECT year, month, sales_contact_id, branch_id FROM credit_note
        UNION ALL SELECT year, month, sales_contact_id, branch_id FROM outstanding
        UNION ALL SELECT year, month, sales_contact_id, branch_id FROM penalty_outstanding
        UNION ALL SELECT year, month, sales_contact_id, branch_id FROM payment
        UNION ALL SELECT year, month, sales_contact_id, branch_id FROM shipping
    ) sub WHERE sales_contact_id IS NOT NULL
),

-- 8) Combine + คำนวณ net_rental
--    net = (rental − CN) + payment − outstanding − shipping
final_calc AS (
    SELECT
        ak.year, ak.month, ak.sales_contact_id, ak.branch_id,
        rb.name AS branch_name,
        rp.name AS sales_contact_name,
        ru.employee_code AS employee_code,
        (COALESCE(r.rental_amount, 0) - COALESCE(cn.cn_amount, 0)) AS rental,
        COALESCE(pmt.payment_received, 0) AS payment,
        (COALESCE(o.outstanding_debt, 0) + COALESCE(po.penalty_amount, 0)) AS outstanding,
        COALESCE(sh.shipping_cost, 0) AS shipping
    FROM all_keys ak
    LEFT JOIN res_branch rb ON rb.id = ak.branch_id
    LEFT JOIN res_users ru ON ru.id = ak.sales_contact_id
    LEFT JOIN res_partner rp ON rp.id = ru.partner_id
    LEFT JOIN rental r ON r.year = ak.year AND r.month = ak.month
        AND r.sales_contact_id = ak.sales_contact_id
        AND r.branch_id IS NOT DISTINCT FROM ak.branch_id
    LEFT JOIN credit_note cn ON cn.year = ak.year AND cn.month = ak.month
        AND cn.sales_contact_id = ak.sales_contact_id
        AND cn.branch_id IS NOT DISTINCT FROM ak.branch_id
    LEFT JOIN outstanding o ON o.year = ak.year AND o.month = ak.month
        AND o.sales_contact_id = ak.sales_contact_id
        AND o.branch_id IS NOT DISTINCT FROM ak.branch_id
    LEFT JOIN penalty_outstanding po ON po.year = ak.year AND po.month = ak.month
        AND po.sales_contact_id = ak.sales_contact_id
        AND po.branch_id IS NOT DISTINCT FROM ak.branch_id
    LEFT JOIN payment pmt ON pmt.year = ak.year AND pmt.month = ak.month
        AND pmt.sales_contact_id = ak.sales_contact_id
        AND pmt.branch_id IS NOT DISTINCT FROM ak.branch_id
    LEFT JOIN shipping sh ON sh.year = ak.year AND sh.month = ak.month
        AND sh.sales_contact_id = ak.sales_contact_id
        AND sh.branch_id IS NOT DISTINCT FROM ak.branch_id
),

-- 9) Detail rows
detail_rows AS (
    SELECT
        year::text || '-' || LPAD(month::text, 2, '0') AS period_label,
        branch_id::text AS branch_code,
        branch_name AS branch_label,
        employee_code AS emp_code,
        sales_contact_name AS sales_name,
        ROUND(rental::numeric, 2) AS rental_amount,
        ROUND(payment::numeric, 2) AS payment_received,
        ROUND(outstanding::numeric, 2) AS outstanding_debt,
        ROUND(shipping::numeric, 2) AS shipping_cost,
        ROUND((rental + payment - outstanding - shipping)::numeric, 2) AS net_rental,
        year AS sort_year, month AS sort_month, 0 AS sort_order,
        branch_id AS sort_branch_id, sales_contact_id AS sort_sales_id
    FROM final_calc
),

-- 10) Subtotal per month — "▶ รวมเดือน YYYY-MM"
subtotal_rows AS (
    SELECT
        year::text || '-' || LPAD(month::text, 2, '0') AS period_label,
        NULL::text AS branch_code,
        '▶ รวมเดือน ' || year::text || '-' || LPAD(month::text, 2, '0') AS branch_label,
        NULL::text AS emp_code,
        NULL::text AS sales_name,
        ROUND(SUM(rental)::numeric, 2) AS rental_amount,
        ROUND(SUM(payment)::numeric, 2) AS payment_received,
        ROUND(SUM(outstanding)::numeric, 2) AS outstanding_debt,
        ROUND(SUM(shipping)::numeric, 2) AS shipping_cost,
        ROUND(SUM(rental + payment - outstanding - shipping)::numeric, 2) AS net_rental,
        year AS sort_year, month AS sort_month, 1 AS sort_order,
        NULL::int AS sort_branch_id, NULL::int AS sort_sales_id
    FROM final_calc GROUP BY year, month
),

-- 11) Grand total per year — "★ รวมทั้งปี YYYY"
grand_total_rows AS (
    SELECT
        year::text || '-99' AS period_label,
        NULL::text AS branch_code,
        '★ รวมทั้งปี ' || year::text AS branch_label,
        NULL::text AS emp_code,
        NULL::text AS sales_name,
        ROUND(SUM(rental)::numeric, 2) AS rental_amount,
        ROUND(SUM(payment)::numeric, 2) AS payment_received,
        ROUND(SUM(outstanding)::numeric, 2) AS outstanding_debt,
        ROUND(SUM(shipping)::numeric, 2) AS shipping_cost,
        ROUND(SUM(rental + payment - outstanding - shipping)::numeric, 2) AS net_rental,
        year AS sort_year, 99 AS sort_month, 2 AS sort_order,
        NULL::int AS sort_branch_id, NULL::int AS sort_sales_id
    FROM final_calc GROUP BY year
)

SELECT
    period_label     AS "เดือน",
    branch_code      AS "รหัสสาขา",
    branch_label     AS "สาขา",
    emp_code         AS "รหัสพนักงาน",
    sales_name       AS "Sales ที่ติดต่อ",
    rental_amount    AS "ยอดเช่า",
    payment_received AS "รับชำระหนี้",
    outstanding_debt AS "หนี้ค้างชำระ",
    shipping_cost    AS "ค่าขนส่ง",
    net_rental       AS "ยอดเช่าสุทธิ"
FROM (
    SELECT * FROM detail_rows
    UNION ALL SELECT * FROM subtotal_rows
    UNION ALL SELECT * FROM grand_total_rows
) all_rows
ORDER BY sort_year ASC, sort_month ASC, sort_order ASC,
         sort_branch_id ASC NULLS LAST, sort_sales_id ASC NULLS LAST;
