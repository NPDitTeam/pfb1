# -*- coding: utf-8 -*-
# ===========================================================================
#  ย้ายสาขาของคลัง "ขายตามสภาพ" ไปเก็บที่ scrap_branch_id   [Server Action]
# ===========================================================================
#  ใช้หลังอัปเกรดโมดูล npd_scrap_buttons เวอร์ชันที่มีฟิลด์ scrap_branch_id
#
#  ทำอะไร
#    1. เติม scrap_branch_id ให้คลังลูก โดยจับคู่จากชื่อคลัง = ชื่อสาขา
#    2. ล้าง branch_id ออก (ถ้ายังมี) กันไม่ให้ไปแย่งผลค้นหาคลังต้นทาง
#    3. ติ๊ก scrap_location ให้ครบ เพื่อให้ปุ่ม Scraps บนใบคืนโผล่
#
#  รันซ้ำได้ ไม่พังอะไร
#
#  วิธีใช้ : Server Action -> โมเดล "Server Action" (ir.actions.server)
#           ชนิด "ดำเนินการโค้ด Python" -> วางโค้ดนี้ -> บันทึก -> เริ่มทำงาน
# ===========================================================================

KEYWORD = 'ขายตามสภาพ'

out = []
Location = env['stock.location']
Branch = env['res.branch']

locs = Location.search([('complete_name', 'ilike', KEYWORD)])
out.append('คลังที่พบ : %d' % len(locs))
out.append('')

n_set = n_clear = n_flag = n_skip = 0
for loc in locs:
    changed = []

    # 1) เติม scrap_branch_id จากชื่อคลัง (คลังแม่ไม่มีสาขา จะข้ามไป)
    if not loc.scrap_branch_id:
        branch = Branch.search([('name', '=', loc.name)], limit=1)
        if branch:
            loc.write({'scrap_branch_id': branch.id})
            changed.append('สาขา=%s' % branch.name)
            n_set += 1

    # 2) ล้าง branch_id (ตัวการที่ทำให้ตัดสต๊อกผิดคลัง)
    if loc.branch_id:
        loc.write({'branch_id': False})
        changed.append('ล้าง branch_id')
        n_clear += 1

    # 3) ติ๊ก scrap_location ให้ปุ่ม Scraps โผล่
    if not loc.scrap_location:
        loc.write({'scrap_location': True})
        changed.append('ติ๊ก scrap_location')
        n_flag += 1

    if changed:
        out.append('  %-40s %s' % (loc.complete_name, ' / '.join(changed)))
    else:
        n_skip += 1

if n_set or n_clear or n_flag:
    env.cr.commit()

out.append('')
out.append('เติมสาขา %d | ล้าง branch_id %d | ติ๊ก scrap_location %d | ไม่ต้องแก้ %d'
           % (n_set, n_clear, n_flag, n_skip))

# --- ตรวจผล ---
out.append('')
out.append('=== ผลลัพธ์ ===')
for loc in locs:
    out.append('  %-40s branch_id=%-10s scrap_branch=%-12s scrap_loc=%s' % (
        loc.complete_name,
        loc.branch_id.name or '-',
        loc.scrap_branch_id.name or '-',
        loc.scrap_location))

# --- กันพลาด: ต้องไม่มีคลังขายตามสภาพเหลือ branch_id ---
still_bad = locs.filtered(lambda l: l.branch_id)
out.append('')
if still_bad:
    out.append('*** ยังมีคลังที่ผูก branch_id อยู่ %d คลัง - ต้องแก้! ***' % len(still_bad))
else:
    out.append('ไม่มีคลังไหนผูก branch_id แล้ว - การตัดสต๊อกปลอดภัย')

raise UserError('\n'.join(out))
