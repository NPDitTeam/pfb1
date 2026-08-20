# -*- coding: utf-8 -*-
# ===========================================================================
#  สร้างคลัง "ขายตามสภาพ" รายสาขา + Reason Code   [เวอร์ชันสำหรับ Server Action]
# ===========================================================================
#  ใช้เมื่อเข้า shell ของเครื่อง production ไม่ได้
#
#  วิธีใช้
#    1. เปิด Developer Mode
#    2. การตั้งค่า -> เทคนิค -> การดำเนินการ -> การดำเนินการเซิร์ฟเวอร์ -> สร้าง
#         ชื่อ    : สร้างคลังขายตามสภาพ
#         โมเดล  : ตำแหน่งสินค้าคงคลัง   (stock.location)
#         ชนิด    : ดำเนินการโค้ด Python  (Execute Python Code)
#    3. วางโค้ดทั้งไฟล์นี้ลงในช่องโค้ด แล้วบันทึก
#    4. กด "รันด้วยตนเอง" -> จะขึ้นกล่องบอกว่าจะสร้างอะไรบ้าง (ยังไม่บันทึกจริง)
#    5. ถ้าถูกต้อง แก้ DRY_RUN = False แล้วกดรันอีกครั้ง
#       -> คราวนี้สร้างจริง และเปิดหน้ารายการคลังที่สร้างให้ดูเลย
#    6. เสร็จแล้วลบ Server Action นี้ทิ้งได้
#
#  หมายเหตุ: Server Action ไม่มีคำสั่ง print / ไม่ควรประกาศ def
#            โค้ดนี้จึงเก็บข้อความไว้ในลิสต์แล้วโยนออกทาง UserError แทน
# ===========================================================================

PARENT_NAME = 'ขายตามสภาพ'
REASON_CODE_NAME = 'ขายตามสภาพ'
DRY_RUN = True

out = []
Location = env['stock.location']

# --- 1) คลังแม่: อิงตำแหน่งของคลัง 'สินค้าชำรุด' เพื่อให้โครงสร้างเหมือนกัน ---
damaged = Location.search([('name', 'ilike', 'ชำรุด'), ('usage', '=', 'internal')])
if len(damaged) != 1:
    raise UserError(
        'ต้องเจอคลัง "สินค้าชำรุด" แบบ Internal เพียง 1 คลัง แต่เจอ %d คลัง:\n%s\n\n'
        'กรุณาแก้เงื่อนไขค้นหาในโค้ดให้ชี้คลังที่ถูกต้องก่อน'
        % (len(damaged), '\n'.join(damaged.mapped('complete_name'))))

root = damaged.location_id
company = damaged.company_id
out.append('โหมด        : %s' % ('DRY RUN - ยังไม่บันทึก' if DRY_RUN else 'สร้างจริง'))
out.append('คลังอ้างอิง : %s' % damaged.complete_name)
out.append('จะสร้างใต้   : %s' % root.complete_name)
out.append('บริษัท      : %s' % company.name)
out.append('-' * 45)

# --- 2) คลังแม่ 'ขายตามสภาพ' ---
parent = Location.search([('name', '=', PARENT_NAME), ('location_id', '=', root.id)], limit=1)
if parent:
    out.append('มีอยู่แล้ว : %s' % parent.complete_name)
elif DRY_RUN:
    out.append('จะสร้าง   : %s/%s' % (root.complete_name, PARENT_NAME))
else:
    parent = Location.create({
        'name': PARENT_NAME,
        'location_id': root.id,
        'usage': 'internal',
        'company_id': company.id,
    })
    out.append('สร้างแล้ว : %s' % parent.complete_name)

# --- 3) คลังลูกรายสาขา (เฉพาะสาขาที่มีคลังสต็อกจริงอยู่แล้ว) ---
branches = Location.search([
    ('usage', '=', 'internal'), ('branch_id', '!=', False),
]).mapped('branch_id')
out.append('-' * 45)
out.append('สาขาที่พบ : %d สาขา' % len(branches))

n_new = 0
n_old = 0
for branch in branches:
    child = False
    if parent:
        child = Location.search([
            ('location_id', '=', parent.id), ('scrap_branch_id', '=', branch.id),
        ], limit=1)
    if child:
        n_old += 1
        out.append('  มีอยู่แล้ว : %s' % child.complete_name)
    elif DRY_RUN:
        n_new += 1
        out.append('  จะสร้าง   : %s/%s' % (PARENT_NAME, branch.name))
    else:
        child = Location.create({
            'name': branch.name,
            'location_id': parent.id,
            'usage': 'internal',
            # ห้ามใช้ branch_id! จะไปแย่งผลค้นหาคลังต้นทางของโมดูลอื่น
            # จนระบบตัดสต๊อกผิดคลัง -> ใช้ scrap_branch_id แทน
            'scrap_branch_id': branch.id,
            'scrap_location': True,
            'company_id': company.id,
        })
        n_new += 1
        out.append('  สร้างแล้ว : %s' % child.complete_name)

# --- 4) Reason Code (ทาง A: รู้ตั้งแต่ตอนรับคืนว่าซ่อมไม่ได้) ---
# location_id = คลังแม่ -> ตอนบันทึกโมดูลจะเลื่อนไปคลังลูกของสาขาต้นทางให้เอง
# is_damage_repair = False -> ใบจบเป็น 'เสร็จสิ้น' ทันที ไม่เข้าคิวซ่อม
#   ฟิลด์นี้มาจาก npd_scrap_buttons ถ้ายังไม่ได้ติดตั้งโมดูล จะข้ามไปก่อน
#   (ค่าเริ่มต้นของฟิลด์คือ False อยู่แล้ว ตอนติดตั้งโมดูลทีหลังจึงถูกต้องเอง)
out.append('-' * 45)
has_reason_model = 'scrap.reason.code' in env
has_repair_flag = bool(env['ir.model.fields'].sudo().search_count([
    ('model', '=', 'scrap.reason.code'), ('name', '=', 'is_damage_repair'),
]))

if not has_reason_model:
    out.append('ข้าม Reason Code : ยังไม่ได้ติดตั้งโมดูล scrap_reason_code')
else:
    vals = {'location_id': parent.id if parent else False}
    if has_repair_flag:
        vals['is_damage_repair'] = False
    else:
        out.append('หมายเหตุ : ยังไม่มีฟิลด์ is_damage_repair (ยังไม่ได้ติดตั้ง npd_scrap_buttons)')
        out.append('           ค่าเริ่มต้นเป็น False อยู่แล้ว ไม่ต้องแก้อะไรทีหลัง')
    Reason = env['scrap.reason.code']
    reason = Reason.search([('name', '=', REASON_CODE_NAME)], limit=1)
    if DRY_RUN:
        out.append('%s Reason Code "%s"' % (
            'จะอัปเดต' if reason else 'จะสร้าง', REASON_CODE_NAME))
    elif reason:
        reason.write(vals)
        out.append('อัปเดต Reason Code : %s' % reason.name)
    else:
        vals['name'] = REASON_CODE_NAME
        reason = Reason.create(vals)
        out.append('สร้าง Reason Code  : %s' % reason.name)

out.append('-' * 45)

# --- 5) จบงาน ---
# DRY RUN : โยน UserError -> ขึ้นกล่องข้อความ และ rollback ทั้งหมด (ไม่มีอะไรถูกบันทึก)
# สร้างจริง: ไม่โยน error -> Odoo commit ตามปกติ แล้วเปิดหน้ารายการคลังให้ตรวจ
if DRY_RUN:
    out.append('DRY RUN จบแล้ว - จะสร้างคลังใหม่ %d คลัง (มีอยู่แล้ว %d)' % (n_new, n_old))
    out.append('ถ้าถูกต้อง ให้แก้ DRY_RUN = False แล้วกดรันอีกครั้ง')
    raise UserError('\n'.join(out))

log('\n'.join(out))
action = {
    'type': 'ir.actions.act_window',
    'name': 'คลังขายตามสภาพ (สร้างใหม่ %d คลัง)' % n_new,
    'res_model': 'stock.location',
    'view_mode': 'tree,form',
    'domain': [('id', 'child_of', parent.id)],
    'target': 'current',
}
