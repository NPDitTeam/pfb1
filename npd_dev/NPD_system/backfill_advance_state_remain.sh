#!/bin/bash
# =============================================================================
# Backfill: account.advance ที่เคลียร์ครบแล้วแต่ค้าง state_remain = 'Wait Clear'
# รันบน server:  bash backfill_advance_state_remain.sh
#
# สาเหตุ: _compute_remaining เทียบ `adv.remain == 0` กับค่า float
#         ผลบวกใบเคลียร์ (เช่น 933.92 + 66.08) ได้ 1000.0000000000001
#         remain เหลือเศษ ~1e-13 -> ตกเป็น Wait Clear และค้างในรายงาน Ageing
#
# แก้โค้ดแล้ว 2 ไฟล์ (float_is_zero / ตัด override ที่ซ้ำใน account_dynamic_reports)
# แต่ Odoo ไม่ recompute stored field ของแถวเดิม จึงต้องรันสคริปต์นี้ 1 ครั้ง
#
# เงื่อนไข abs(remain) < 0.005 = น้อยกว่าครึ่งสตางค์ -> ใบที่ค้างจริงไม่โดนแตะ
# =============================================================================
set -euo pipefail

DBS="NPD_Bangkok_New NPD_Intertrading_New NPD_Intertrading_New_NonVat NPD_Logistics_New NPD_S_Group_New_V2 NPD_Steeltech_New acc_data_Intertrading_2025 acc_data_Sgroup_2025"
DBC=npd_production_db_1
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=/root/rollback-advance-state_remain-$STAMP
mkdir -p "$OUT"

echo "== 1) สำรองค่าเดิมไว้ที่ $OUT =="
for DB in $DBS; do
  docker exec -i "$DBC" psql -U odoo -d "$DB" -At <<'SQL' > "$OUT/$DB.sql"
SELECT 'UPDATE account_advance SET remain=' || remain
    || ', state_remain=' || quote_literal(state_remain)
    || ' WHERE id=' || id || ';'
FROM account_advance
WHERE state_remain = 'Wait Clear' AND remain <> 0 AND abs(remain) < 0.005;
SQL
  printf "   %-30s %s แถว\n" "$DB" "$(wc -l < "$OUT/$DB.sql")"
done

echo
echo "== 2) Backfill =="
for DB in $DBS; do
  N=$(docker exec -i "$DBC" psql -U odoo -d "$DB" -At <<'SQL'
BEGIN;
WITH upd AS (
  UPDATE account_advance
  SET remain = 0, state_remain = 'Clear'
  WHERE state_remain = 'Wait Clear' AND remain <> 0 AND abs(remain) < 0.005
  RETURNING 1
) SELECT count(*) FROM upd;
COMMIT;
SQL
)
  printf "   %-30s แก้ %s ใบ\n" "$DB" "$N"
done

echo
echo "== 3) ตรวจผล (ต้องได้ 0 ทุก DB) =="
for DB in $DBS; do
  N=$(docker exec -i "$DBC" psql -U odoo -d "$DB" -At \
      -c "SELECT count(*) FROM account_advance WHERE remain <> 0 AND abs(remain) < 0.005;")
  printf "   %-30s เหลือเศษ %s\n" "$DB" "$N"
done

echo
echo "เสร็จแล้ว"
echo "ถ้าต้อง rollback:"
echo "  for f in $OUT/*.sql; do docker exec -i $DBC psql -U odoo -d \$(basename \$f .sql) -f - < \$f; done"
