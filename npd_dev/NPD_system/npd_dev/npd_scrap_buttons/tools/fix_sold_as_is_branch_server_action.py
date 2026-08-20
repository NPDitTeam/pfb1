# -*- coding: utf-8 -*-
# ===========================================================================
#  แก้ด่วน: ล้าง branch_id ออกจากคลัง "ขายตามสภาพ"   [Server Action]
# ===========================================================================
#  อาการ : ยืนยันใบส่งของ/ตัดสต๊อกไม่ได้ ขึ้น Validation Error ว่าสต๊อกจะติดลบ
#          ที่คลัง 'W2/ขายตามสภาพ/<สาขา>'
#
#  สาเหตุ : โมดูลเดิม (stock_move_line_auto_fill ฯลฯ) หาคลังต้นทางด้วย
#              search([('branch_id','=',x), ('usage','=','internal')], limit=1)
#           โดยไม่ระบุ order เอง จึงใช้ _order ของ stock.location
#           = 'complete_name, id'  ->  'W2/ขายตามสภาพ/..' (ข) มาก่อน
#                                      'W2/บริษัท นภดล../..' (บ)
#           พอคลังขายตามสภาพผูก branch_id ด้วย ระบบจึงไปตัดสต๊อกผิดคลัง
#
#  วิธีแก้ : เอา branch_id ออกจากคลังขายตามสภาพ (คลังยังอยู่ ของยังอยู่)
#           การอ้างอิงสาขาของคลังกลุ่มนี้จะย้ายไปใช้ฟิลด์เฉพาะแทนในโมดูลรุ่นถัดไป
#
#  วิธีใช้ : Server Action -> โมเดล "Server Action" (ir.actions.server)
#           ชนิด "ดำเนินการโค้ด Python" -> วางโค้ดนี้ -> บันทึก -> เริ่มทำงาน
#           (แก้ทันที ไม่มีโหมด DRY RUN เพราะเป็นการแก้ของที่พังอยู่)
# ===========================================================================

KEYWORD = 'ขายตามสภาพ'

out = []
Location = env['stock.location']

# --- 1) ล้าง branch_id ---
bad = Location.search([('complete_name', 'ilike', KEYWORD), ('branch_id', '!=', False)])
out.append('คลังที่ล้าง branch_id : %d คลัง' % len(bad))
for loc in bad:
    out.append('   %s' % loc.complete_name)
    # ต้องเขียนทีละตัว: constraint _check_branch ของโมดูล branch เป็นแบบ singleton
    loc.write({'branch_id': False})

if bad:
    env.cr.commit()
    out.append('>>> บันทึกแล้ว')
else:
    out.append('   (ไม่มีคลังที่ต้องแก้ - แก้ไปแล้ว หรือยังไม่ได้สร้างคลัง)')

# --- 2) ตรวจซ้ำว่าทุกสาขาชี้คลังถูกต้องแล้ว ---
out.append('')
out.append('=== ตรวจซ้ำ: คลังที่ระบบจะเลือกให้แต่ละสาขา ===')
branches = Location.search([
    ('usage', '=', 'internal'), ('branch_id', '!=', False),
]).mapped('branch_id')

n_bad = 0
for branch in branches:
    first = Location.search([
        ('branch_id', '=', branch.id), ('usage', '=', 'internal'),
    ], limit=1)
    is_bad = KEYWORD in (first.complete_name or '')
    if is_bad:
        n_bad += 1
    out.append('  %s %-14s -> %s' % ('ผิด!' if is_bad else 'ถูก ', branch.name, first.complete_name))

# --- 3) เช็คว่ามีของหลงไปอยู่ในคลังขายตามสภาพหรือยัง ---
out.append('')
out.append('=== ของค้างในคลังขายตามสภาพ (ควรว่างเปล่า) ===')
locs = Location.search([('complete_name', 'ilike', KEYWORD)])
quants = env['stock.quant'].search([('location_id', 'in', locs.ids)])
if not quants:
    out.append('  ไม่มีของค้าง - ปลอดภัย')
else:
    for q in quants:
        out.append('  %s | %s | %s' % (q.location_id.complete_name, q.product_id.display_name, q.quantity))
    out.append('  *** มีของค้าง/ติดลบ ต้องปรับสต๊อกให้ถูกต้องก่อน ***')

out.append('')
out.append('สรุป : %s' % ('ปกติทุกสาขาแล้ว' if n_bad == 0 else 'ยังผิดอยู่ %d สาขา' % n_bad))
raise UserError('\n'.join(out))
