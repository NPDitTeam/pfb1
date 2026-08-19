# -*- coding: utf-8 -*-
"""สร้างคลัง "ขายตามสภาพ" รายสาขา + Reason Code สำหรับตัดของเข้าคลังนั้น

รันซ้ำได้ ไม่สร้างซ้ำ (idempotent) — ใช้ได้ทั้งตอนขึ้นระบบครั้งแรกและตอนเปิดสาขาใหม่

โครงสร้างที่ได้
    <คลังแม่เดียวกับ 'สินค้าชำรุด'>/ขายตามสภาพ        (internal, ไม่ผูกสาขา)
        └── ขายตามสภาพ/<ชื่อสาขา>                     (internal, ผูก branch_id)

ทำไมต้อง internal : ของต้องยังอยู่ในสต็อกถึงจะเปิดบิลขายมือสองได้
ทำไมต้องแยกรายสาขา : รายงานภาพรวมสต็อก เช่า นับ "ยอดคงเหลือรอขาย" แยกตามสาขา
ทำไมชื่อต้องมีคำว่า 'ขายตามสภาพ' : SQL ของรายงานใช้คำนี้แยกคลังนี้ออกจากของพร้อมใช้งาน

--------------------------------------------------------------------------
วิธีรัน แบบที่ 1 — odoo shell (มี shell access ที่เครื่อง production)
--------------------------------------------------------------------------
    odoo-bin shell -c odoo.conf -d <DB> --no-http

  แล้ววางบรรทัดนี้ (แก้ path ให้ตรงเครื่อง) — อย่า pipe ไฟล์เข้า stdin ตรง ๆ
  เพราะ console บน Windows จะทำภาษาไทยเพี้ยน:

    exec(compile(open(r'<path>/setup_sold_as_is.py', encoding='utf-8').read(), 'setup', 'exec'))

--------------------------------------------------------------------------
วิธีรัน แบบที่ 2 — Server Action ในหน้าเว็บ (ไม่ต้องมี shell)
--------------------------------------------------------------------------
  เปิด Developer Mode -> การตั้งค่า -> เทคนิค -> การดำเนินการ -> การดำเนินการเซิร์ฟเวอร์
  สร้างใหม่: Model = Stock Location, ชนิด = Execute Python Code
  วางเนื้อไฟล์นี้ลงไป แล้วตั้ง COMMIT_AT_END = False (Odoo commit ให้เองตอนจบ)
  กด "รันด้วยตนเอง" หนึ่งครั้ง เสร็จแล้วลบ Server Action ทิ้งได้
--------------------------------------------------------------------------
"""

# ===== ตั้งค่า =====
PARENT_NAME = 'ขายตามสภาพ'
REASON_CODE_NAME = 'ขายตามสภาพ'
# True  = แสดงว่าจะสร้างอะไรบ้าง แต่ไม่บันทึกจริง (ควรรันแบบนี้ก่อนเสมอบน production)
# False = สร้างจริง
DRY_RUN = True
# odoo shell ต้อง commit เอง / Server Action ให้ตั้งเป็น False
COMMIT_AT_END = True
# ===================

Location = env['stock.location']

# --- 1) หาคลังแม่: อิงจากที่อยู่ของคลัง 'สินค้าชำรุด' เพื่อให้โครงสร้างเหมือนกัน ---
damaged = Location.search([
    ('name', 'ilike', 'ชำรุด'), ('usage', '=', 'internal'),
])
if len(damaged) != 1:
    raise Exception(
        'ต้องเจอคลัง "สินค้าชำรุด" แบบ internal เพียง 1 คลัง แต่เจอ %d คลัง: %s\n'
        'กรุณาระบุคลังแม่เองโดยแก้ตัวแปร damaged ในสคริปต์'
        % (len(damaged), damaged.mapped('complete_name')))

root = damaged.location_id
company = damaged.company_id
print('คลังอ้างอิง : %s' % damaged.complete_name)
print('จะสร้างใต้   : %s (บริษัท %s)' % (root.complete_name, company.name))
print('โหมด        : %s' % ('DRY RUN (ไม่บันทึก)' if DRY_RUN else 'สร้างจริง'))
print('-' * 70)

# --- 2) คลังแม่ 'ขายตามสภาพ' ---
parent = Location.search([
    ('name', '=', PARENT_NAME), ('location_id', '=', root.id),
], limit=1)
if parent:
    print('มีอยู่แล้ว : %s' % parent.complete_name)
elif DRY_RUN:
    print('จะสร้าง   : %s/%s' % (root.complete_name, PARENT_NAME))
else:
    parent = Location.create({
        'name': PARENT_NAME,
        'location_id': root.id,
        'usage': 'internal',
        'company_id': company.id,
    })
    print('สร้างแล้ว : %s' % parent.complete_name)

# --- 3) คลังลูกรายสาขา (เฉพาะสาขาที่มีคลังสต็อกจริงอยู่แล้ว) ---
branches = Location.search([
    ('usage', '=', 'internal'), ('branch_id', '!=', False),
]).mapped('branch_id')
print('-' * 70)
print('สาขาที่พบ : %d สาขา' % len(branches))

created = existed = planned = 0
for branch in branches:
    child = parent and Location.search([
        ('location_id', '=', parent.id), ('branch_id', '=', branch.id),
    ], limit=1)
    if child:
        existed += 1
        print('  มีอยู่แล้ว : %s' % child.complete_name)
    elif DRY_RUN:
        planned += 1
        print('  จะสร้าง   : %s/%s  (branch %s)' % (PARENT_NAME, branch.name, branch.id))
    else:
        child = Location.create({
            'name': branch.name,
            'location_id': parent.id,
            'usage': 'internal',
            'branch_id': branch.id,
            'company_id': company.id,
        })
        created += 1
        print('  สร้างแล้ว : %s' % child.complete_name)

# --- 4) Reason Code (ทาง A: รู้ตั้งแต่ตอนรับคืนว่าซ่อมไม่ได้) ---
# location_id = คลังแม่ -> ตอนบันทึกโมดูลจะเลื่อนไปคลังลูกของสาขาต้นทางให้เอง
# is_damage_repair = False -> ใบจบเป็น 'เสร็จสิ้น' ทันที ไม่เข้าคิวซ่อม
#   ฟิลด์นี้มาจาก npd_scrap_buttons ถ้ายังไม่ได้ติดตั้งโมดูล จะข้ามไปก่อน
#   (ค่าเริ่มต้นของฟิลด์คือ False อยู่แล้ว ตอนติดตั้งโมดูลทีหลังจึงถูกต้องเอง)
print('-' * 70)
has_reason_model = 'scrap.reason.code' in env
has_repair_flag = bool(env['ir.model.fields'].sudo().search_count([
    ('model', '=', 'scrap.reason.code'), ('name', '=', 'is_damage_repair'),
]))

if not has_reason_model:
    print('ข้าม Reason Code : ยังไม่ได้ติดตั้งโมดูล scrap_reason_code')
else:
    vals = {'location_id': parent.id if parent else False}
    if has_repair_flag:
        vals['is_damage_repair'] = False
    else:
        print('หมายเหตุ : ยังไม่มีฟิลด์ is_damage_repair (ยังไม่ได้ติดตั้ง npd_scrap_buttons)')
        print('           ค่าเริ่มต้นเป็น False อยู่แล้ว ไม่ต้องแก้อะไรทีหลัง')
    Reason = env['scrap.reason.code']
    reason = Reason.search([('name', '=', REASON_CODE_NAME)], limit=1)
    if DRY_RUN:
        print('%s Reason Code "%s" -> %s' % (
            'จะอัปเดต' if reason else 'จะสร้าง', REASON_CODE_NAME,
            parent.complete_name if parent else PARENT_NAME))
    elif reason:
        reason.write(vals)
        print('อัปเดต Reason Code : %s -> %s' % (reason.name, parent.complete_name))
    else:
        vals['name'] = REASON_CODE_NAME
        reason = Reason.create(vals)
        print('สร้าง Reason Code  : %s -> %s' % (reason.name, parent.complete_name))

print('-' * 70)
if DRY_RUN:
    print('DRY RUN จบแล้ว — จะสร้างคลังลูกใหม่ %d คลัง (มีอยู่แล้ว %d)' % (planned, existed))
    print('ถ้าถูกต้องแล้ว ให้แก้ DRY_RUN = False แล้วรันซ้ำ')
else:
    if COMMIT_AT_END:
        env.cr.commit()
    print('เสร็จสิ้น — สร้างคลังลูกใหม่ %d คลัง (มีอยู่แล้ว %d)' % (created, existed))
