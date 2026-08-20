# -*- coding: utf-8 -*-
# ===========================================================================
#  ย้ายของที่คืนผิดคลัง ออกจาก "ขายตามสภาพ" กลับคลังสาขา   [Server Action]
# ===========================================================================
#  อาการ : ช่วงที่คลังขายตามสภาพยังผูก branch_id อยู่ ระบบเลือกคลังปลายทาง
#          ผิด ทำให้ของที่ลูกค้าคืนวิ่งเข้าคลังขายตามสภาพแทนคลังสาขา
#
#  สคริปต์นี้ทำอะไร
#    1. ไล่ดู move ทุกตัวที่วิ่งเข้าคลังขายตามสภาพ แล้วแยกว่าอันไหนถูก/ผิด
#         ถูก : ชื่อ move ตรงกับเลขที่ใบ Scrap (SP/xxxxx) = มาจากใบ Scrap จริง
#               หรือขึ้นต้นด้วย 'Sold as is' = มาจากปุ่มซ่อมไม่สำเร็จ
#         ผิด : นอกเหนือจากนั้น = ของที่คืนเข้ามาผิดคลัง
#    2. ย้ายเฉพาะส่วนที่ผิดกลับไปคลังสาขาที่ถูกต้อง
#       (จำกัดไม่เกินยอดคงเหลือจริงในคลัง เผื่อบางส่วนถูกเบิกออกไปแล้ว)
#
#  ต้องรันหลังแก้ branch_id เรียบร้อยแล้ว เพราะต้องใช้หาคลังสาขาที่ถูกต้อง
#
#  วิธีใช้ : Server Action -> โมเดล "Server Action" (ir.actions.server)
#           ชนิด "ดำเนินการโค้ด Python" -> วางโค้ดนี้ -> บันทึก -> เริ่มทำงาน
#           รันครั้งแรกเป็น DRY RUN ดูรายการก่อน ถ้าถูกต้องแก้ DRY_RUN = False
# ===========================================================================

KEYWORD = 'ขายตามสภาพ'
DRY_RUN = True

out = []
Location = env['stock.location']
Move = env['stock.move']
Quant = env['stock.quant']

locs = Location.search([('complete_name', 'ilike', KEYWORD)])
if not locs:
    raise UserError('ไม่พบคลัง "%s" ในระบบ' % KEYWORD)

# --- กันพลาด: ถ้ายังมีคลังผูก branch_id อยู่ แปลว่ายังไม่ได้แก้ต้นเหตุ ---
still_bad = locs.filtered(lambda l: l.branch_id)
if still_bad:
    raise UserError(
        'ยังมีคลังขายตามสภาพที่ผูก branch_id อยู่ %d คลัง\n%s\n\n'
        'ต้องรันสคริปต์ migrate_scrap_branch ก่อน ไม่งั้นของจะไหลกลับมาผิดอีก'
        % (len(still_bad), '\n'.join(still_bad.mapped('complete_name'))))

out.append('โหมด : %s' % ('DRY RUN - ยังไม่ย้ายจริง' if DRY_RUN else 'ย้ายจริง'))
out.append('')

# --- 1) แยก move ถูก/ผิด ---
# move ของใบ Scrap ตั้งชื่อเป็นเลขที่ใบเสมอ (_prepare_move_values ใช้ self.name)
# จึงเช็คทั้งจากรายชื่อใบที่มีอยู่ และจาก prefix ของ sequence เผื่อใบถูกลบไปแล้ว
scrap_names = set(env['stock.scrap'].search([]).mapped('name'))
sequence = env['ir.sequence'].sudo().search([('code', '=', 'stock.scrap')], limit=1)
scrap_prefix = sequence.prefix or 'SP/'

moves_in = Move.search([
    ('location_dest_id', 'in', locs.ids), ('state', '=', 'done'),
])

wrong_qty = {}       # (location_id, product_id, dest_id) -> จำนวนที่เข้ามาผิด
wrong_moves = []
no_dest = []
for mv in moves_in:
    name = mv.name or ''
    if name in scrap_names or name.startswith(scrap_prefix) or name.startswith('Sold as is'):
        continue

    # ปลายทางที่ถูกต้อง: เอาสาขาจากคลัง ถ้าคลังแม่ไม่มีสาขา ใช้สาขาของใบโอนย้ายแทน
    branch = mv.location_dest_id.scrap_branch_id or mv.picking_id.branch_id
    dest = Location.search([
        ('branch_id', '=', branch.id), ('usage', '=', 'internal'),
    ], limit=1) if branch else Location.browse()

    wrong_moves.append(mv)
    if not dest:
        no_dest.append(mv)
        continue
    key = (mv.location_dest_id.id, mv.product_id.id, dest.id)
    wrong_qty[key] = wrong_qty.get(key, 0.0) + mv.product_qty

out.append('=== move ที่วิ่งเข้าคลังขายตามสภาพ: %d รายการ ===' % len(moves_in))
out.append('  มาจากใบ Scrap (ถูกต้อง) : %d' % (len(moves_in) - len(wrong_moves)))
out.append('  คืนเข้ามาผิดคลัง        : %d' % len(wrong_moves))
for mv in wrong_moves:
    out.append('     %-32s %-10s จาก %s' % (
        mv.product_id.display_name[:32], mv.product_qty,
        mv.picking_id.name or mv.origin or '-'))

if no_dest:
    out.append('')
    out.append('*** หาสาขาปลายทางไม่ได้ %d รายการ - ต้องย้ายเองด้วยมือ ***' % len(no_dest))
    for mv in no_dest:
        out.append('     %-32s %-8s อยู่ที่ %s' % (
            mv.product_id.display_name[:32], mv.product_qty, mv.location_dest_id.complete_name))

if not wrong_qty:
    out.append('')
    out.append('ไม่มีรายการที่ย้ายกลับอัตโนมัติได้')
    raise UserError('\n'.join(out))

# --- 2) วางแผนย้ายกลับ (จำกัดไม่เกินของที่เหลือจริง) ---
out.append('')
out.append('=== แผนการย้ายกลับ ===')
plan = []
used = {}     # (location_id, product_id) -> จำนวนที่จองไปแล้วในแผน
for (loc_id, product_id, dest_id), qty in sorted(wrong_qty.items()):
    loc = Location.browse(loc_id)
    dest = Location.browse(dest_id)
    product = env['product.product'].browse(product_id)

    quants = Quant.search([
        ('location_id', '=', loc_id), ('product_id', '=', product_id),
    ])
    taken = used.get((loc_id, product_id), 0.0)
    available = sum(quants.mapped('quantity')) - taken
    move_qty = min(qty, available)
    note = '' if move_qty == qty else '  (เหลือจริง %s จากที่เข้ามาผิด %s)' % (available, qty)
    if move_qty <= 0:
        out.append('  ข้าม %-28s %s : ไม่มีของเหลือแล้ว' % (
            product.display_name[:28], loc.complete_name))
        continue

    used[(loc_id, product_id)] = taken + move_qty
    out.append('  %-30s %8s  %s  ->  %s%s' % (
        product.display_name[:30], move_qty, loc.name, dest.name, note))
    plan.append((loc, product, move_qty, dest, quants))

# --- 3) ย้ายจริง ---
if not DRY_RUN and plan:
    for loc, product, qty, dest, quants in plan:
        lot = quants[0].lot_id if quants and quants[0].lot_id else False
        move = Move.create({
            'name': 'แก้คืนสต๊อกผิดคลัง: %s -> %s' % (loc.name, dest.name),
            'origin': 'FIX-SOLD-AS-IS',
            'company_id': loc.company_id.id or env.company.id,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': qty,
            'location_id': loc.id,
            'location_dest_id': dest.id,
            'state': 'draft',
            'picking_id': False,
            'picking_type_id': False,
            'move_line_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'qty_done': qty,
                'location_id': loc.id,
                'location_dest_id': dest.id,
                'lot_id': lot.id if lot else False,
            })],
        })
        move._action_done()
    env.cr.commit()

out.append('')
if DRY_RUN:
    out.append('DRY RUN จบแล้ว - จะย้ายกลับ %d รายการ' % len(plan))
    out.append('ถ้าถูกต้อง ให้แก้ DRY_RUN = False แล้วกดรันอีกครั้ง')
else:
    out.append('ย้ายกลับเรียบร้อย %d รายการ' % len(plan))
    out.append('ตรวจได้ที่ สินค้าคงคลัง -> รายงาน -> สต็อกปัจจุบัน')

raise UserError('\n'.join(out))
