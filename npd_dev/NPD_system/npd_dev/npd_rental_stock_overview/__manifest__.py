# -*- coding: utf-8 -*-
{
    'name': 'NPD Rental Stock Overview',
    'version': '14.0.1.2.0',
    'summary': 'รายงานภาพรวมสต็อก เช่า แยกสาขา พร้อมจำนวนที่ถูกเช่า (ตัดสต๊อกเสร็จสิ้น ยังไม่คืน)',
    'description': """
รายงานภาพรวมสต็อก เช่า
======================
แสดงรายการสินค้าทั้งหมดแยกตามสาขา (res.branch) พร้อมคอลัมน์:
  * ปริมาณคงคลัง (on-hand) ของสาขา
  * จำนวนที่ถูกเช่า = จำนวนที่ตัดสต๊อกออก (ใบส่งออกสถานะ 'เสร็จสิ้น') ของบิลเช่า
    ที่ 'ยังไม่ได้คืนครบ' (หักจำนวนที่คืนกลับผ่านใบคืนที่เสร็จสิ้นแล้ว)

นิยาม 'จำนวนที่ถูกเช่า' ใช้ตรรกะเดียวกับ so_auto_stock_cut (_compute_sc_stock_flags):
  ใบตัด = ใบส่งออก (picking_type=outgoing) สถานะ done ที่ไม่ใช่ใบคืน
  จำนวนที่คืน = move ที่อ้างอิงกลับผ่าน origin_returned_move_id (state done)
  จำนวนที่ถูกเช่า(สุทธิ) = จำนวนตัด - จำนวนคืน  (ต่อสินค้า+สาขา)
""",
    'author': 'NPD',
    'category': 'Inventory/Reporting',
    # npd_scrap_buttons: ต้องใช้สถานะ pending_repair/under_repair/repaired,
    # ฟิลด์ repair_deadline และ widget npd_repair_countdown ของคอลัมน์รอซ่อม 48 ชม.
    'depends': ['stock', 'sale_stock', 'branch', 'npd_scrap_buttons'],
    'data': [
        'security/ir.model.access.csv',
        'views/rental_stock_overview_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
