# -*- coding: utf-8 -*-
# ===========================================================================
#  ทำให้ปุ่ม "Scraps" บนใบโอนย้าย/ใบคืน โผล่ครบทุกประเภท   [Server Action]
# ===========================================================================
#  อาการ : ทำสินค้าหาย -> ปุ่ม Scraps มุมขวาบนขึ้น
#          ทำสินค้าชำรุด -> ปุ่มไม่ขึ้น
#
#  สาเหตุ : stock.move.scrapped เป็นฟิลด์ related แบบ stored
#              scrapped = related('location_dest_id.scrap_location', store=True)
#           และปุ่มซ่อนตาม has_scrap_move ที่นับเฉพาะ move ที่ scrapped = True
#           คลัง 'สินค้าหาย' ติ๊ก scrap_location ไว้ -> ปุ่มขึ้น
#           คลัง 'สินค้าชำรุด' ไม่ได้ติ๊ก            -> ปุ่มไม่ขึ้น
#
#  วิธีแก้ : ติ๊ก "Is a Scrap Location?" ให้คลังปลายทางของ Reason Code ทุกตัว
#           Odoo จะคำนวณ scrapped ของ move เดิมย้อนหลังให้เองอัตโนมัติ
#           (ไม่กระทบ usage ของคลัง ของยังอยู่ในสต็อกเหมือนเดิม)
#
#  วิธีใช้ : Server Action -> โมเดล "Server Action" (ir.actions.server)
#           ชนิด "ดำเนินการโค้ด Python" -> วางโค้ดนี้ -> บันทึก -> เริ่มทำงาน
# ===========================================================================

out = []
Location = env['stock.location']

# --- 1) รวบรวมคลังปลายทางที่ใช้จริง: จาก Reason Code ทุกตัว + คลังขายตามสภาพ ---
targets = env['scrap.reason.code'].search([]).mapped('location_id')
targets |= Location.search([('complete_name', 'ilike', 'ขายตามสภาพ')])
targets |= env['stock.scrap'].search([]).mapped('scrap_location_id')

out.append('คลังปลายทางที่ตรวจ : %d คลัง' % len(targets))
out.append('')
out.append('=== ก่อนแก้ ===')
for loc in targets:
    out.append('  %-42s usage=%-10s scrap_location=%s' % (
        loc.complete_name, loc.usage, loc.scrap_location))

# --- 2) ติ๊ก scrap_location ---
to_fix = targets.filtered(lambda l: not l.scrap_location)
out.append('')
out.append('=== ติ๊ก scrap_location ให้ %d คลัง ===' % len(to_fix))
for loc in to_fix:
    # เขียนทีละตัว: constraint _check_branch ของโมดูล branch เป็นแบบ singleton
    loc.write({'scrap_location': True})
    out.append('  ติ๊กแล้ว : %s' % loc.complete_name)
if not to_fix:
    out.append('  (ติ๊กครบอยู่แล้ว ไม่ต้องแก้อะไร)')

# --- 3) ตรวจว่าไม่มีใบโอนย้ายไหนถูกเปลี่ยนสถานะโดยไม่ตั้งใจ ---
# stock.picking.state เป็น compute+store และสูตรใช้ move.scrapped
# จะกลายเป็น 'ยกเลิก' ก็ต่อเมื่อ move ที่เสร็จสิ้นเป็น scrap ทั้งหมด
# และมี move ที่ถูกยกเลิกซึ่งไม่ใช่ scrap ปนอยู่
moves = env['stock.move'].search([('location_dest_id', 'in', targets.ids)])
pickings = moves.mapped('picking_id')
out.append('')
out.append('=== ตรวจใบโอนย้ายที่เกี่ยวข้อง %d ใบ ===' % len(pickings))
states = {}
risky = []
for pk in pickings:
    states[pk.state] = states.get(pk.state, 0) + 1
    done_moves = pk.move_lines.filtered(lambda m: m.state == 'done')
    cancel_moves = pk.move_lines.filtered(lambda m: m.state == 'cancel')
    if done_moves and all(m.scrapped for m in done_moves) and any(not m.scrapped for m in cancel_moves):
        risky.append(pk.name)
for st in sorted(states):
    out.append('  %-12s %d ใบ' % (st, states[st]))
if risky:
    out.append('  *** ใบที่อาจถูกเปลี่ยนเป็นยกเลิก: %s ***' % ', '.join(risky[:10]))
else:
    out.append('  ไม่มีใบไหนเสี่ยงถูกเปลี่ยนสถานะ - ปลอดภัย')

if to_fix:
    env.cr.commit()
    out.append('')
    out.append('>>> บันทึกแล้ว - เปิดใบคืนใหม่ ปุ่ม Scraps จะขึ้นทั้งสินค้าหายและสินค้าชำรุด')

raise UserError('\n'.join(out))
