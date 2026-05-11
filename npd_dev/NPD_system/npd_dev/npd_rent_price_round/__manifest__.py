{
    'name': 'NPD Rent Price Subtotal Rounding',
    'version': '14.0.1.0.32',
    'category': 'Sales',
    'summary': 'ปัดเศษราคาต่อหน่วยหลังถอด VAT ให้ตรงกับรายงาน',
    'description': """
v14.0.1.0.32: แก้ใบเงินประกัน/ใบไม่มี VAT ติ๊ก vat_from_total อัตโนมัติ
+ ยอดไม่ตรง
เคสที่เจอ: SO เช่า (VAT 7%) → กดปุ่ม "รับเงินประกัน" → สร้างใบเงินประกัน
(ไม่มี VAT) แต่ flag vat_from_total สืบมาจาก SO ผ่าน _prepare_invoice
→ Method B บวก 7% เกินมาบน subtotal ที่ไม่ใช่ VAT
→ ยอด 2,000 กลายเป็น 2,140 (เกิน 140 บาท)
แก้ 2 จุด:
1) Method B tax-aware: ใน _npd_force_round_sql ส่วน move totals
   - คิด 7% เฉพาะ subtotal ของ line ที่มี 7% VAT inclusive จริงๆ
   - บรรทัดที่ไม่มี VAT (เช่น เงินประกัน) → ไม่บวก 7%
   - บรรทัดที่มี WHT → ใช้สูตร per-line เดิม (รวมเข้า tax)
2) Auto-untick vat_from_total ใน account.move.create():
   - หลัง super().create() เช็คว่า move นี้มี invoice_line_ids ที่
     ผูก tax 7% inclusive หรือไม่
   - ถ้าไม่มี → SQL update vat_from_total = FALSE (move + lines)
   - + invalidate cache → _npd_force_round_sql ที่ตามมาเห็นค่าใหม่
- ผลกระทบ: ใบเงินประกัน/ใบไม่มี VAT → field ไม่ติ๊ก ยอดถูกต้องตาม line จริง

v14.0.1.0.31: รีเซ็ต vat_from_total = FALSE ให้เอกสารเก่าทั้งหมด
สาเหตุ: ตอน v14.0.1.0.27 เพิ่ม field vat_from_total (default=True) — Odoo's
`_init_column` backfill ค่า TRUE ให้แถวเก่าทุกแถวอัตโนมัติ ทำให้เอกสารเก่า
ติ๊กฟิลด์ใหม่โดยไม่ตั้งใจ
แก้: เพิ่ม post-migration script ที่ migrations/14.0.1.0.31/
- UPDATE sale_order/account_move SET vat_from_total = FALSE (ทุกแถว)
- Sync ลง sale_order_line / account_move_line (related store=True)
- หลัง migration: เอกสารเก่า → FALSE, เอกสารใหม่ที่สร้างต่อไป → TRUE (จาก default)
Pattern เดียวกับ v14.0.1.0.4 ที่ reset use_new_calc ตอน introduce field

v14.0.1.0.30: แก้ "Cannot create unbalanced journal entry" บน button_cancel
ของใบรับชำระ/Payment receipt
สาเหตุ: ตั้งแต่ v14.0.1.0.13 เพิ่ม self._check_balanced() ใน write/create
override (และ v14.0.1.0.29 ใน action_post) เพื่อ validate หลังจากปิด
check_move_validity ของ Odoo ระหว่างทาง — แต่เป็นการเช็คแบบไม่ดู state
→ ตอน user กดยกเลิกใบรับชำระ:
  1) state เปลี่ยน posted → cancel ผ่าน write({'state': 'cancel'})
  2) Odoo's button_cancel อาจ unreconcile / ปรับ line ระหว่างทาง
     → state ชั่วคราว unbalanced (Odoo ไม่ check เพราะ state=cancel)
  3) write override ของเราเรียก _check_balanced ตามมา → เจอ unbalanced
     → raise error → user ยกเลิกไม่ได้
แก้: ตรวจสมดุลเฉพาะ moves ที่ state == 'posted' AND มี line_ids เท่านั้น
ใน 3 จุด: create, write, action_post
- draft state: ไม่ต้องตรวจ (Odoo เองก็ไม่ตรวจ)
- cancel state: ไม่ต้องตรวจ (cancelled moves ไม่กระทบบัญชี)
- เฉพาะ posted: ตรวจสมดุลเข้มงวด (เคารพ semantics ของ Odoo)
ผลกระทบ: ใบรับชำระ/payment receipt ที่ถูกสร้างก่อน v14.0.1.0.27
สามารถยกเลิกได้ตามปกติ ไม่กระทบ flow Method A/B ของใบใหม่

v14.0.1.0.29: แก้ "Cannot create unbalanced journal entry" บน action_post
เมื่อ vat_from_total=True
สาเหตุ: ระหว่าง super().action_post() Odoo's _post() อาจเรียก
_recompute_tax_lines/_recompute_dynamic_lines ซึ่ง reset tax line กลับเป็น
สูตรเดิม (per-line round = 621.74) → ไม่ตรงกับ receivable ที่ Method B
rebalance ไว้ (9,504.00) → debit-credit ไม่ตรงกัน 0.02-0.04 บาท
แก้: ทำ pattern เดียวกับ write override:
1) _npd_force_round_sql ก่อน super() — เตรียม balanced state
2) wrap super() ใน check_move_validity=False — ปิด _check_balanced ของ Odoo
   ระหว่างทาง (ป้องกัน fail ที่ intermediate state)
3) _npd_force_round_sql หลัง super() — re-apply Method A/B + rebalance
4) self._check_balanced() เอง — ตรวจสมดุลขั้นสุดท้าย

v14.0.1.0.28: [Phase 2] ขยาย vat_from_total ไปถึง account.move + payment
- _prepare_invoice ของ sale.order: ส่ง vat_from_total ไปยัง invoice อัตโนมัติ
- เพิ่ม field vat_from_total บน account.move (default=True, copy=True, tracking=True)
- เพิ่ม related field vat_from_total บน account.move.line (store=True)
- ขยาย _npd_force_round_sql ฝั่ง account.move.line:
  * Detect moves ที่ติ๊ก vat_from_total ผ่าน SQL (early-return guard ใหม่)
  * Tax line rebalance: ถ้าใช้ Method B และเป็น VAT 7% →
      tax = round(SUM(price_subtotal) × 0.07, 2) (ปัดครั้งเดียว)
  * Move totals: ถ้าใช้ Method B →
      tax = round(amount_untaxed × 0.07, 2)
  * Order priority: target_amount_total > Method B > default per-line sum
  * Method B ใช้กับภาษี 7% เท่านั้น — ภาษี WHT อื่นใช้สูตรเดิม
- เพิ่ม onchange ของ account.move รวม vat_from_total (รีเฟรชฟอร์ม)
- เพิ่ม checkbox 'คำนวณ VAT จากยอดรวม' บนฟอร์ม invoice
- พฤติกรรมที่ได้: SO → Invoice → Payment ใช้ amount_total ตรงกันทั้งสาย
- รวมถึง: tax line balance, account.move.tax.invoice (l10n_th),
  receivable rebalance, amount_residual sync — ทุกอย่างคำนวณจาก Method B
ข้อจำกัดที่รู้:
- รายงานใบกำกับภาษี (PDF) ยังคงอ่านจาก amount_tax/amount_total ของ Odoo
  → ตอนนี้ค่าใน DB ตรงกับ Method B แล้ว → ไม่ต้องแก้ template ใดๆ

v14.0.1.0.27: [POC ฝั่ง SO] เพิ่ม flag คำนวณ VAT จากยอดรวม (Method B)
- เพิ่ม field vat_from_total บน sale.order (default=True, copy=True, tracking=True)
- เพิ่ม related field vat_from_total บน sale.order.line (store=True)
- แก้ _npd_force_round_sql: เมื่อ order.vat_from_total=True →
    amount_tax = round(amount_untaxed × 0.07, 2)  (ปัดครั้งเดียวที่ระดับ order)
    แทนที่ผลรวมของ price_tax ที่ปัดรายบรรทัด (สูตรเดิม)
- แก้ _npd_sync_baan_kheaw_orders: รองรับ Method B เช่นกัน
- เพิ่ม checkbox 'คำนวณ VAT จากยอดรวม' บนฟอร์ม SO ข้าง use_baan_kheaw
- เพิ่ม vat_from_total ใน invalidate_cache ของ _npd_recalc_amounts
- write hook ของ sale.order: trigger recompute เมื่อ flag เปลี่ยน
พฤติกรรม:
- SO เก่าใน DB (vat_from_total=NULL→False) ใช้สูตรเดิม ยอดไม่กระทบ
- SO ใหม่ default=True → amount_tax/amount_total เปลี่ยนเป็น Method B
- Duplicate (copy=True) → สืบทอดค่าจาก source
ขอบเขต POC: ฝั่ง SO เท่านั้น ใบแจ้งหนี้/ใบลดหนี้/ผ่อนชำระ ยังคงใช้สูตร Odoo
default จาก SO line — เฟสถัดไปจะขยายไป account.move + rebalance tax line
ข้อจำกัดที่รู้:
- ถ้า use_new_calc=False และ use_baan_kheaw=False (no Method A active),
  _npd_force_round_sql จะ early return และ Method B จะไม่ทำงาน
  → ไม่กระทบ scenario ใบเช่าซึ่ง use_new_calc=True เสมอ

ปรับการคำนวณ price_subtotal ของ sale.order.line และ account.move.line
โดยปัดเศษ price_unit / 1.07 ให้เหลือ 2 ตำแหน่งก่อนคูณ qty

v14.0.1.0.4: เพิ่มฟิลด์ use_new_calc ที่ sale.order และ account.move
เพื่อแยก "ใบเก่า" (ใช้สูตรระบบเดิม) ออกจาก "ใบใหม่" (ใช้สูตรใหม่)
ค่านี้ส่งต่อ SO -> Invoice -> Credit Note อัตโนมัติ

v14.0.1.0.6: แก้ปัญหาแก้ไขราคาในฟอร์ม account.move (Invoice / Debit Note /
Credit Note) แล้วยอดไม่อัปเดต โดยเพิ่ม @api.onchange('price_unit_no_vat')
เพื่อ sync price_unit และเรียก _onchange_price_subtotal ของ Odoo ให้
recompute price_subtotal / price_total / debit / credit / amount_currency
ทันทีในฟอร์ม (เดิมเป็น inverse-only ซึ่งไม่ trigger onchange chain)

v14.0.1.0.7: แก้ปัญหา "Cannot create unbalanced journal entry" ตอนสร้าง
ใบแจ้งหนี้/ใบลดหนี้/Debit Note ที่ method A ทำให้ subtotal เปลี่ยนจากสูตรเดิม
0.01-0.6 บาท สาเหตุ: _npd_force_round_sql เปลี่ยน debit/credit ของ invoice line
แต่ tax line + receivable/payable line ยังเป็นค่าเดิม → debit ≠ credit
แก้: หลัง update invoice line แล้ว recompute tax line จาก
sum(base.price_subtotal) × tax.amount/100 และ rebalance receivable/payable
ให้ผลรวม debit-credit = 0 (กรณีผ่อนหลายงวด รับ delta ที่งวดแรก
เพื่อรักษาสัดส่วนการแบ่งงวด)

v14.0.1.0.8: แก้ปัญหาวิกฤติ — Advance Clear / Bank Statement / Manual Entry
และ document อื่นใดๆ ที่สร้าง account.move.line ด้วย debit/credit ตรงๆ
(ไม่ผ่าน price_unit × qty) ทำให้ post ไม่ผ่าน "Cannot create unbalanced
journal entry" เพราะ method A ใช้ price_unit=0 (default) → คำนวณ subtotal=0
→ SQL update ทับ debit เดิมเป็น 0 → debit หาย ตามจำนวน line ที่มี VAT 7% incl
แก้: เพิ่ม guard 2 ชั้นใน _npd_compute_method_a:
1) ข้ามถ้า move ไม่ใช่ invoice/receipt (move_type='entry' จะข้ามทันที)
2) ข้ามถ้า price_unit = 0 (defense in depth)

v14.0.1.0.9: เพิ่ม security group "แก้ไข Use New Calculation ได้"
ใน category "NPD Rent Price Round" (ปรากฏในแท็บ Access Rights ของ user form)
- User ที่อยู่ใน group → ติ๊ก/ยกเลิก use_new_calc บน SO/Invoice ได้เอง
- User ที่ไม่ได้อยู่ใน group → ฟิลด์ readonly (พฤติกรรมเดิม)
- Logic การคำนวณ method A ไม่เปลี่ยน

v14.0.1.0.10: เปลี่ยนจาก security group เป็น Boolean field
"can_edit_use_new_calc" บน res.users ตรงๆ (เลิกใช้ ir.module.category +
res.groups เพื่อไม่กระทบการแสดงผลของ user form)
- เพิ่มแท็บ "NPD Settings" ในฟอร์ม user → checkbox "แก้ไข Use New
  Calculation ได้"
- ติ๊ก = user คนนั้นแก้ไข use_new_calc บน SO/Invoice ได้
- ไม่ติ๊ก = readonly เหมือนเดิม
- หมายเหตุ: ถ้าเคยใช้ v14.0.1.0.9 มาก่อน ให้ลบ orphan records
  module_category_use_new_calc_editing และ group_use_new_calc_editor
  ผ่าน UI หรือ SQL (records จะค้างใน DB แต่ไม่กระทบการทำงาน)

v14.0.1.0.11: ปรับ UI label และเพิ่ม flag "ใช้ราคาจากบ้านเขียว"
- เปลี่ยน label ของ use_new_calc จาก "Use New Calculation" เป็น
  "คิดราคาต่อหน่วยแบบถอด Vat" (ทั้ง sale.order และ account.move)
- เพิ่ม field use_baan_kheaw บน sale.order (เฉพาะฝั่ง SO ตามคำขอ)
  - ติ๊ก: ข้าม Method A ทั้งหมด, ใช้สูตร Odoo default
  - ยอด amount_untaxed/tax/total sync ตาม sale_order_line ปกติ
- เมื่อ toggle use_new_calc หรือ use_baan_kheaw ระบบจะ recompute
  ยอดทั้ง order ทันทีผ่าน _npd_recalc_amounts
- หลัง Method A อัพเดท tax_line แล้ว → sync account.move.tax.invoice
  (l10n_th_tax_invoice) ให้ tax_base_amount + balance ตรงกับยอดใหม่

v14.0.1.0.12: ขยาย flag use_baan_kheaw ให้ใช้ฝั่ง account.move ด้วย
ปัญหาเดิม: ฝั่ง SO ติ๊ก use_baan_kheaw แล้วยอดถูกต้อง แต่พอสร้าง
ใบแจ้งหนี้ flag ไม่ถูกส่งไปยัง account.move → Method A ยังทำงาน →
ยอดใบแจ้งหนี้คำนวณผิดจาก SO
แก้:
- เพิ่ม field use_baan_kheaw บน account.move + account.move.line (related)
- _prepare_invoice ส่งค่า use_baan_kheaw จาก SO ไป invoice อัตโนมัติ
- _npd_compute_method_a ของ account.move.line ข้าม line ที่ติ๊ก
  use_baan_kheaw (เหมือนฝั่ง SO)
- _compute_price_unit_no_vat / _inverse_price_unit_no_vat /
  _onchange_price_unit_no_vat รองรับ use_baan_kheaw ด้วย
  (use_baan_kheaw=True → ราคาแสดงตรง = price_unit incl VAT)
- เพิ่ม _npd_compute_baan_kheaw_reset เพื่อรองรับกรณี toggle ใน UI
  หลัง Method A เคยเขียน DB ทับค่าเก่า → reset เป็นสูตร Odoo default
  + rebalance tax/receivable/move totals
- เพิ่ม onchange บน account.move ให้รีเฟรช price_unit_no_vat ของ
  invoice line ทันทีเมื่อ toggle flag

v14.0.1.0.13: แก้ปัญหา "Cannot create unbalanced journal entry" บนใบลดหนี้
(out_refund) เมื่อ use_new_calc=True (ติ๊กเฉพาะ "คิดราคาต่อหน่วยแบบถอด Vat"
อย่างเดียว ไม่ติ๊ก use_baan_kheaw)
สาเหตุ: ระหว่าง super().write() ของ Odoo
  1) _recompute_tax_lines ลบ tax line เก่า → cascade ลบ
     account.move.tax.invoice (l10n_th_tax_invoice)
  2) สร้าง/อัปเดต tax line ใหม่ตามสูตร Odoo default
  3) _check_balanced ถูกเรียกก่อนที่ Method A ของเราจะปรับ subtotal +
     rebalance — debit/credit ไม่ตรงกัน VAT amount = diff
แก้: ใส่ context check_move_validity=False ใน super().write/create เพื่อ
ปิดการเช็ค balance ของ Odoo ระหว่างทาง แล้วเรียก _check_balanced เอง
หลังรัน _npd_force_round_sql เสร็จ (ซึ่งจะ rebalance ครบทุกบรรทัด)
ใช้ pattern เดียวกับที่ Odoo ใช้ใน account.move.write (line 2116)

v14.0.1.0.26: ขยายปุ่ม "แก้ไขยอดทศนิยม" ให้แสดงบน:
- ใบแจ้งหนี้ (out_invoice)
- Vendor Bill (in_invoice)
- ใบลดหนี้ (out_refund)
- Vendor Refund (in_refund)
- Debit Note (out_invoice/in_invoice ที่มี debit_origin_id — ครอบคลุมโดย
  out_invoice/in_invoice อยู่แล้ว)
- view: เพิ่ม out_invoice, in_invoice ใน attrs invisible
- action_open_decimal_adjust_wizard: ขยาย allowed_types
- wizard description / labels เปลี่ยนจาก "ใบลดหนี้" เป็น "เอกสาร" generic

v14.0.1.0.25: ขยายขอบเขต "กำหนดเอง" ใน wizard
- เดิม: ±0.05 บาท (เกินจะ reject)
- ใหม่: < 1.00 บาท (อนุญาตทศนิยมใดๆ เช่น 0.27, -0.95)
- แยก constants:
  PRESET_MAX_ABS = 0.05  (สำหรับ selection options)
  CUSTOM_LIMIT = 1.0     (สำหรับ custom field — strict <)
- Validate ใน action_apply แยก path:
  custom path → check < CUSTOM_LIMIT
  preset path → check ≤ PRESET_MAX_ABS
- Onchange warning ของ custom field ใช้ CUSTOM_LIMIT
- Help text update

v14.0.1.0.24: แก้ปัญหา "กดปรับยอดรอบแรก ยอดไม่เปลี่ยน ต้องกดซ้ำ"
- สาเหตุ 1: ORM ยัง buffer pending writes ของ target_amount_total อยู่ใน
  cache ตอน _npd_force_round_sql รัน SQL queries → SELECT อ่านค่าเก่า
  → has_target = False → ใช้ formula natural Method A → ยอดไม่เปลี่ยน
- แก้: เพิ่ม env['account.move'].flush() + env['account.move.line'].flush()
  ที่ start ของ _npd_force_round_sql → บังคับ ORM commit ลง DB ก่อน
  SQL reads
- สาเหตุ 2: act_window_close ของ Odoo ไม่ trigger parent form refresh
  by default → ต้องคลิกซ้ำเพื่อให้ form อ่านค่าใหม่
- แก้: wizard return เพิ่ม 'infos': {'reload': True} → Odoo 14 action
  manager จะ re-read parent record หลัง wizard ปิด (ไม่ใช่ full page
  reload, แค่ data refresh)
- เพิ่ม helper _flush_and_refresh ใน wizard รวม flush + invalidate +
  return action เป็น method เดียว

v14.0.1.0.23: เปลี่ยน wizard return จาก reload (full page) เป็น
act_window_close (close wizard เท่านั้น, parent form auto-refresh)
- เพิ่ม method _refresh_move_cache ใน wizard:
  invalidate ORM cache ของฟิลด์ที่ถูก SQL update ใน _npd_force_round_sql
  เช่น amount_total, amount_tax, amount_residual, line balances ฯลฯ
- หลัง invalidate → parent form อ่านค่าใหม่จาก DB ตอน wizard ปิด
- UX ดีขึ้น: ไม่ flicker ทั้งหน้าเหมือน reload tag

v14.0.1.0.22: แก้ปัญหา wizard "แก้ไขยอดทศนิยม"
1. amount_residual update แต่ amount_total ไม่ update (ไม่ sync กัน)
   - สาเหตุ: ORM cache ของ target_amount_total ไม่ตรงกับ DB ทำให้
     has_target = False ใน _npd_force_round_sql
   - แก้: อ่าน target_amount_total จาก DB ตรงๆ ผ่าน SQL (target_value_by_move
     dict) bypass ORM cache
   - เพิ่ม SQL UPDATE amount_residual ของ receivable line + move หลัง
     update line.balance (เพราะ stored compute ไม่ recompute จาก SQL)
2. ลด selection options ใน wizard เหลือ ±0.01, ±0.02, ±0.05 + custom + reset
   (เอา ±0.10, ±0.20 ออก — เกินขอบเขต wizard)
3. Custom field: validate |value| ≤ 0.05 ผ่าน onchange warning
4. action_apply: return reload action ('ir.actions.client', 'reload')
   เพื่อให้ form refresh เห็นยอดใหม่ทันที
5. MAX_ABS_ADJUSTMENT = 0.05 (ลดจากเดิม 1.00)

v14.0.1.0.21: แก้ access error ของ wizard npd.adjust.decimal.wizard
- เพิ่ม security/ir.model.access.csv ให้สิทธิ์ base.group_user (Internal User)
  read/write/create/unlink wizard records
- TransientModel ที่สร้างใหม่ต้องประกาศ access right ให้ user group
  ใช้งานได้ (Odoo standard) ไม่งั้นเจอ "No group currently allows
  this operation"
- โหลด csv ก่อน wizard view ใน data list

v14.0.1.0.20: เปลี่ยน UX ของ target_amount_total — จากฟิลด์เปิดให้แก้
ตรงๆ ในฟอร์ม → ใช้ wizard popup "แก้ไขยอดทศนิยม" แทน
เหตุผล: ป้องกัน user เผลอกรอกยอดผิด — wizard จำกัดการปรับเป็น
ขั้นเล็กๆ (±0.01-0.20) เหมาะกับการ fine-tune rounding เท่านั้น
- ลบ field target_amount_total ออกจากฟอร์ม (ตั้ง invisible=1, เก็บใน DB
  เพื่อ tracking)
- เพิ่มปุ่ม "แก้ไขยอดทศนิยม" บน header (xpath after action_register_payment)
  visible เฉพาะ out_refund/in_refund
- เพิ่ม method action_open_decimal_adjust_wizard บน account.move
- สร้าง wizard model npd.adjust.decimal.wizard (TransientModel):
  * แสดงยอดรวมปัจจุบัน
  * Selection field: ±0.01, ±0.02, ±0.05, ±0.10, ±0.20, custom, reset
  * แสดง preview ยอดหลังปรับ
  * action_apply: set move.target_amount_total = current + delta
    (เรียก _npd_force_round_sql ผ่าน write hook)
  * Reset option: ตั้ง target = 0 → กลับเป็น Method A ปกติ
  * Safety: max abs delta 1.00 บาท + ยอดใหม่ต้อง > 0
- สร้าง wizard view + register action

v14.0.1.0.19: ย้าย field "ยอดเป้าหมาย" ไปอยู่ในส่วน totals (subtotal
footer) ใต้ field "รวม" — UI สอดคล้องกับฟิลด์ยอดรวมอื่นๆ
- เปลี่ยน xpath จาก partner_id position="after" → amount_total position="after"
- เพิ่ม widget="monetary" + options currency_field
- ฟิลด์จะแสดงเป็นยอดรูปแบบ Monetary (มี currency suffix) เหมือน amount_total

v14.0.1.0.18: ขยาย target_amount_total ให้ใช้กับใบลดหนี้ที่
use_new_calc=False ได้ด้วย (เคสเก่า)
- ปรับ _npd_force_round_sql: ตรวจ moves_with_target_ids ก่อน early return
  ถ้ามี move ที่ตั้ง target_amount_total > 0 → รัน rebalance flow
  แม้ไม่มี line ใดถูก Method A / baan_kheaw modify
- เพิ่ม move ที่มี target เข้า moves_changed → trigger tax line +
  receivable + move totals override ใน loop ด้านล่าง
- View: ลบเงื่อนไข use_new_calc ออก เหลือแค่ check move_type
  ใบลดหนี้ทุกใบ (ทั้ง use_new_calc True/False) ใช้ฟีเจอร์นี้ได้

v14.0.1.0.17: เพิ่ม field "ยอดเป้าหมาย (target_amount_total)" บน account.move
สำหรับใบลดหนี้ที่ user ต้องการบังคับยอดรวมให้ตรงเป๊ะตามเงื่อนไขภายใน
- เพิ่ม field target_amount_total: Monetary, default 0.0, copy=False
  (อยู่บน account.move — ไม่ inherit ระหว่าง invoice → credit note)
- View: แสดงเฉพาะ out_refund/in_refund + use_new_calc=True
  (เพราะ Method A ต้องทำงานก่อน vat_from_total ต่อยอด)
- Logic ใน _npd_force_round_sql: ถ้า target_amount_total > 0 →
  * tax line balance = target - SUM(price_subtotal) (override per-line tax)
  * move.amount_tax = target - SUM(price_subtotal)
  * move.amount_total = target (ตรงเป๊ะ)
  * receivable rebalance ตาม sum_other (รวม tax line ใหม่)
- ถ้า target = 0 → ใช้ flow ปกติ (Method A per-line round)
- Workflow: User กรอก target → Save → ระบบปรับยอดอัตโนมัติ
- ข้อจำกัด: ต้องติ๊ก use_new_calc=True (Method A active) เพื่อให้
  _npd_force_round_sql ทำงาน — ถ้า use_new_calc=False target จะไม่ apply

v14.0.1.0.16: แก้ v14.0.1.0.15 ที่ผิด — Odoo 14 ไม่มี column price_tax
ใน account_move_line (เป็น non-stored compute field) ทำให้ SQL UPDATE/SELECT
fail ด้วย UndefinedColumn error
แก้: ใช้ SUM(price_total) - SUM(price_subtotal) แทน SUM(price_tax)
ซึ่งให้ผลเดียวกัน (Method A เขียน price_total = price_subtotal + per-line tax)
- ลบ price_tax ออกจาก _npd_write_subtotal_sql UPDATE
- เปลี่ยน tax line rebalance อ่าน SUM(price_total) แทน
- เปลี่ยน move totals อ่าน SUM(price_total) แทน
- ผลลัพธ์เหมือนเดิม: tax = ผลรวม per-line round = SO total

v14.0.1.0.15: (ผิด — UndefinedColumn price_tax) แก้ Method A tax line

v14.0.1.0.14: บังคับ use_baan_kheaw=True ตลอดสำหรับ Debit Note
- ตรวจ debit_origin_id (field จาก account_debit_note module — set โดย
  wizard เมื่อสร้าง Debit Note จากใบแจ้งหนี้)
- create: ถ้า vals มี debit_origin_id → บังคับ use_baan_kheaw=True
- write: ถ้า move เป็น Debit Note และ user toggle เป็น False
  หรือ vals กำลังตั้ง debit_origin_id → บังคับ use_baan_kheaw=True
- view: field use_baan_kheaw readonly เมื่อ debit_origin_id != False
  (ป้องกัน user toggle ผ่าน UI)
- เหตุผล: Debit Note ต้องใช้ยอดของบ้านเขียวเท่านั้น ไม่ใช้ Method A
    """,
    'author': 'NPD Dev',
    'depends': [
        'sale',
        'account',
        'sale_discount_display_amount',
        'bi_sale_purchase_discount_with_tax',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/adjust_decimal_wizard_views.xml',
        'views/res_users_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'post_init_hook': '_post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
