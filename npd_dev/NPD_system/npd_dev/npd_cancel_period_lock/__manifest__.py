# -*- coding: utf-8 -*-
{
    'name': 'NPD Cancel Period Lock',
    'version': '14.0.1.0.0',
    'summary': 'ล็อกไม่ให้ยกเลิกใบแจ้งหนี้ / ใบรับชำระ ของเดือนก่อนหน้า (ยกเว้นฝ่ายการเงิน)',
    'description': """
NPD Cancel Period Lock
======================
เพิ่มฟิลด์ "สถานะการยกเลิก" ให้

    * ใบแจ้งหนี้   (account.move ประเภท out_invoice) ตัดสินจาก "วันที่ใบแจ้งหนี้"
    * ใบรับชำระ    (account.payment ประเภทรับเงิน inbound) ตัดสินจาก "วันที่รับชำระ"

เอกสารที่วันที่อยู่ก่อน "วันตัดงวด" จะขึ้นสถานะ
"ไม่สามารถยกเลิกได้ โปรดติดต่อฝ่ายการเงิน"
และกดปุ่ม ยกเลิก / รีเซ็ตเป็นแบบร่าง จะขึ้นแจ้งเตือนข้อความเดียวกัน

วันตัดงวด
    ตั้งจาก Scheduled Action "ล็อกการยกเลิกเอกสารเดือนก่อนหน้า" ที่รันทุกวันที่ 15
    เวลา 00:05 (เวลาประเทศไทย) -> วันตัดงวด = วันที่ 1 ของเดือนปัจจุบัน
    เช่น 15/09/2026 เป็นต้นไป เอกสารก่อน 01/09/2026 ยกเลิกไม่ได้
    ใช้เวลาประเทศไทย (Asia/Bangkok) เสมอ ไม่ขึ้นกับ timezone ของเครื่องหรือฐานข้อมูล
    เก็บค่าไว้ที่ System Parameter npd_cancel_period_lock.cutoff_date

สิทธิ์ยกเลิกได้ไม่สนเงื่อนไข: กลุ่ม "Cancel Period Lock - ยกเลิกเอกสารย้อนหลังได้ (ฝ่ายการเงิน)"
เปิดให้ผู้ใช้ได้ที่ ตั้งค่า > ผู้ใช้ > แท็บ Preferences
""",
    'category': 'Accounting',
    'author': 'NPD Dev',
    'license': 'AGPL-3',
    # ต้องโหลดหลังสองโมดูลนี้ เพื่อให้ด่านตรวจของเราทำงานก่อนโค้ดของมัน
    # (account_payment_invoice.action_draft() สั่ง cr.commit() กลางคัน
    #  ถ้าตรวจทีหลัง ของที่มันแก้ไปแล้วจะไม่ถูก rollback)
    'depends': [
        'account',
        'account_payment_invoice',
        'custom_payment_draft',
    ],
    'data': [
        'security/security.xml',
        'data/ir_cron.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/res_users_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
