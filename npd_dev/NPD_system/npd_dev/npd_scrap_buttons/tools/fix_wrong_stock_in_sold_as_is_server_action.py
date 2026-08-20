# -*- coding: utf-8 -*-
# ===========================================================================
#  ย้ายของที่คืนผิดคลัง ออกจาก "ขายตามสภาพ" กลับคลังสาขา   [Server Action]
# ===========================================================================
#  อาการ : ช่วงที่คลังขายตามสภาพยังผูก branch_id อยู่ ระบบเลือกคลังปลายทางผิด
#          ทำให้ของที่ลูกค้าคืนวิ่งเข้าคลังขายตามสภาพแทนคลังสาขา
#
#  สำคัญ : โมดูล stock_move_line_auto_fill เปลี่ยนคลังปลายทางที่ระดับ
#          stock.move.LINE ตัว stock.move ยังชี้คลังสาขาเดิมอยู่
#          จึงต้องตรวจจาก move.line ไม่ใช่ move ไม่งั้นจะหาไม่เจอ
#
#  วิธีคิด : ยึดยอดคงเหลือจริง (stock.quant) เป็นตัวตั้ง
#            ของที่ "ควรอยู่" ในคลังนี้ = เฉพาะที่มาจากใบ Scrap เท่านั้น
#              เข้า(จากใบ Scrap) - ออก(จากใบ Scrap) = ยอดที่ถูกต้อง
#            ส่วนที่เกินจากนั้น = ของที่คืนผิดคลัง ต้องย้ายกลับ
#
#            แยกใบ Scrap จากชื่อ move ซึ่ง Odoo ตั้งเป็นเลขที่ใบเสมอ
#            (_prepare_move_values ใช้ self.name) เช่น SP/01462
#
#  ต้องรันหลังแก้ branch_id เรียบร้อยแล้ว (สคริปต์เช็คให้)
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
MoveLine = env['stock.move.line']
Quant = env['stock.quant']

locs = Location.search([('complete_name', 'ilike', KEYWORD)])
if not locs:
    raise UserError('ไม่พบคลัง "%s" ในระบบ' % KEYWORD)

still_bad = locs.filtered(lambda l: l.branch_id)
if still_bad:
    raise UserError(
        'ยังมีคลังขายตามสภาพที่ผูก branch_id อยู่ %d คลัง\n%s\n\n'
        'ต้องรันสคริปต์ migrate_scrap_branch ก่อน ไม่งั้นของจะไหลกลับมาผิดอีก'
        % (len(still_bad), '\n'.join(still_bad.mapped('complete_name'))))

scrap_names = set(env['stock.scrap'].search([]).mapped('name'))
sequence = env['ir.sequence'].sudo().search([('code', '=', 'stock.scrap')], limit=1)
scrap_prefix = sequence.prefix or 'SP/'

out.append('โหมด : %s' % ('DRY RUN - ยังไม่ย้ายจริง' if DRY_RUN else 'ย้ายจริง'))
out.append('')

quants = Quant.search([('location_id', 'in', locs.ids)]).filtered(lambda q: q.quantity > 0)
out.append('=== ของคงเหลือในคลังขายตามสภาพ: %d รายการ ===' % len(quants))

plan = []
manual = []
for quant in quants:
    loc = quant.location_id
    product = quant.product_id

    lines_in = MoveLine.search([
        ('location_dest_id', '=', loc.id), ('product_id', '=', product.id),
        ('state', '=', 'done'),
    ])
    lines_out = MoveLine.search([
        ('location_id', '=', loc.id), ('product_id', '=', product.id),
        ('state', '=', 'done'),
    ])

    def _is_scrap(line):
        name = line.move_id.name or ''
        return (name in scrap_names or name.startswith(scrap_prefix)
                or name.startswith('Sold as is'))

    scrap_in = sum(l.qty_done for l in lines_in if _is_scrap(l))
    scrap_out = sum(l.qty_done for l in lines_out if _is_scrap(l))
    should_be = max(scrap_in - scrap_out, 0.0)
    wrong = quant.quantity - should_be

    label = '  %-30s %-14s คงเหลือ %-9s จากใบ Scrap %-9s' % (
        product.display_name[:30], loc.name, quant.quantity, should_be)

    if wrong <= 0:
        out.append(label + ' -> ถูกต้องแล้ว')
        continue

    # ปลายทาง: สาขาของคลัง ถ้าไม่มีให้ดูสาขาจากใบโอนย้ายที่ทำให้ของเข้ามาผิด
    branch = loc.scrap_branch_id
    if not branch:
        for line in lines_in:
            if not _is_scrap(line) and line.picking_id.branch_id:
                branch = line.picking_id.branch_id
                break
    dest = Location.search([
        ('branch_id', '=', branch.id), ('usage', '=', 'internal'),
    ], limit=1) if branch else Location.browse()

    if not dest:
        out.append(label + ' -> ต้องย้ายเอง (หาสาขาไม่ได้)')
        manual.append((loc, product, wrong))
        continue

    out.append(label + ' -> ย้ายกลับ %s' % wrong)
    plan.append((loc, product, wrong, dest, quant))

# --- รายละเอียดใบที่ทำให้ของเข้ามาผิด ---
if plan:
    out.append('')
    out.append('=== ใบที่ทำให้ของเข้ามาผิดคลัง ===')
    seen = []
    for loc, product, qty, dest, quant in plan:
        for line in MoveLine.search([
            ('location_dest_id', '=', loc.id), ('product_id', '=', product.id),
            ('state', '=', 'done'),
        ]):
            name = line.move_id.name or ''
            if name in scrap_names or name.startswith(scrap_prefix) or name.startswith('Sold as is'):
                continue
            ref = line.picking_id.name or line.move_id.origin or '-'
            key = '%s|%s' % (ref, product.id)
            if key in seen:
                continue
            seen.append(key)
            out.append('  %-16s %-30s %s' % (ref, product.display_name[:30], line.qty_done))

if manual:
    out.append('')
    out.append('*** ต้องย้ายเองด้วยมือ %d รายการ (หาสาขาปลายทางไม่ได้) ***' % len(manual))
    for loc, product, qty in manual:
        out.append('  %-30s %-8s อยู่ที่ %s' % (product.display_name[:30], qty, loc.complete_name))

# --- ย้ายจริง ---
if not DRY_RUN and plan:
    for loc, product, qty, dest, quant in plan:
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
                'lot_id': quant.lot_id.id if quant.lot_id else False,
                'owner_id': quant.owner_id.id if quant.owner_id else False,
                'package_id': quant.package_id.id if quant.package_id else False,
            })],
        })
        move._action_done()
    env.cr.commit()

out.append('')
if not plan:
    out.append('ไม่มีของที่ต้องย้ายกลับ')
elif DRY_RUN:
    out.append('DRY RUN จบแล้ว - จะย้ายกลับ %d รายการ' % len(plan))
    out.append('ถ้าถูกต้อง ให้แก้ DRY_RUN = False แล้วกดรันอีกครั้ง')
else:
    out.append('ย้ายกลับเรียบร้อย %d รายการ' % len(plan))

raise UserError('\n'.join(out))
