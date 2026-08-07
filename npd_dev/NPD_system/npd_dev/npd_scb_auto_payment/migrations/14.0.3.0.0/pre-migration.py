# -*- coding: utf-8 -*-
u"""ถอด "ระบบ webhook ธนาคารเดิม" ออกจากฐานข้อมูล

โมเดล scb.payment.notification ถูกลบออกจากโค้ดแล้ว ถ้าปล่อยให้ Odoo ไปเก็บกวาด
เองตอน ir.model.data._process_end() มันจะพังด้วย

    KeyError: 'scb.payment.notification'

เพราะ IrModelFieldsSelection.unlink() -> _process_ondelete() เรียก
``self.env[selection.field_id.model]`` กับโมเดลที่ไม่มีใน registry แล้ว
(โค้ด Odoo เองระบุไว้ว่าเคสนี้ต้องจัดการด้วย migration script)

สคริปต์นี้จึงล้าง metadata + ตารางข้อมูลด้วย SQL ตรง ๆ ก่อนโหลดข้อมูลโมดูล
ส่วน ir_model_data ที่เหลือค้าง Odoo จะเก็บกวาดเองได้ตามปกติ
(record.exists() = False -> ลบทิ้งเงียบ ๆ)

*** ตารางและข้อมูลแจ้งเตือน webhook เก่าจะถูกลบถาวร ***
"""
import logging

_logger = logging.getLogger(__name__)

MODEL = 'scb.payment.notification'
TABLE = 'scb_payment_notification'
LEGACY_PAYMENT_COLUMNS = ('scb_auto_created', 'scb_notification_id')
LEGACY_PARAMS = (
    'npd_scb_auto_payment.api_key',
    'npd_scb_auto_payment.scb_method_id',
    'npd_scb_auto_payment.wht_method_id',
    'npd_scb_auto_payment.deposit_method_id',
    'npd_scb_auto_payment.auto_create',
    'npd_scb_auto_payment.auto_post',
    'npd_scb_auto_payment.see_all_branches',
)


def migrate(cr, version):
    if not version:
        return  # ติดตั้งใหม่ ไม่มีของเก่าให้ล้าง

    cr.execute("SELECT 1 FROM ir_model WHERE model = %s", (MODEL,))
    if not cr.fetchone():
        _logger.info("npd_scb_auto_payment: ไม่พบโมเดล %s ในฐานข้อมูล ข้ามการล้าง", MODEL)
        return

    # ------------------------------------------------------------------
    # 1) วิว / action / เมนู ที่ผูกกับโมเดลเก่า
    # ------------------------------------------------------------------
    cr.execute("DELETE FROM ir_ui_view WHERE model = %s", (MODEL,))
    cr.execute("""
        DELETE FROM ir_ui_menu
              WHERE action IN (SELECT 'ir.actions.act_window,' || id
                                 FROM ir_act_window WHERE res_model = %s)
    """, (MODEL,))
    cr.execute("DELETE FROM ir_act_window WHERE res_model = %s", (MODEL,))
    cr.execute("DELETE FROM ir_act_server WHERE model_id IN "
               "(SELECT id FROM ir_model WHERE model = %s)", (MODEL,))

    # ไอคอนแจ้งเตือนบน navbar (systray) — ถอด template ออกด้วย
    cr.execute("""
        DELETE FROM ir_ui_view
              WHERE id IN (SELECT res_id FROM ir_model_data
                            WHERE module = 'npd_scb_auto_payment'
                              AND model = 'ir.ui.view'
                              AND name = 'assets_backend')
    """)

    # ------------------------------------------------------------------
    # 2) ฟิลด์บนโมเดลอื่นที่ชี้มาที่โมเดลเก่า (account.payment.scb_notification_id)
    #    ต้องลบ metadata ก่อน ไม่งั้น _process_end จะไป unlink แล้วสะดุด
    # ------------------------------------------------------------------
    cr.execute("DELETE FROM ir_model_fields WHERE relation = %s", (MODEL,))
    cr.execute("""
        DELETE FROM ir_model_fields
              WHERE model = 'account.payment' AND name IN %s
    """, (LEGACY_PAYMENT_COLUMNS,))

    # ------------------------------------------------------------------
    # 3) metadata ของโมเดลเอง
    #    FK ทุกตัวที่ชี้มา ir_model เป็น ondelete=cascade อยู่แล้ว แต่สั่งลบเรียงลำดับ
    #    เองด้วย เพื่อไม่ให้ผลลัพธ์ขึ้นกับ constraint ที่อาจถูกแก้ไว้ในระบบ
    # ------------------------------------------------------------------
    cr.execute("""
        DELETE FROM ir_model_fields_selection
              WHERE field_id IN (SELECT id FROM ir_model_fields WHERE model = %s)
    """, (MODEL,))
    cr.execute("DELETE FROM ir_model_fields WHERE model = %s", (MODEL,))
    cr.execute("DELETE FROM ir_model_access WHERE model_id IN "
               "(SELECT id FROM ir_model WHERE model = %s)", (MODEL,))
    cr.execute("DELETE FROM ir_rule WHERE model_id IN "
               "(SELECT id FROM ir_model WHERE model = %s)", (MODEL,))
    cr.execute("DELETE FROM ir_model_constraint WHERE model IN "
               "(SELECT id FROM ir_model WHERE model = %s)", (MODEL,))
    cr.execute("DELETE FROM ir_model_relation WHERE model IN "
               "(SELECT id FROM ir_model WHERE model = %s)", (MODEL,))
    cr.execute("DELETE FROM ir_model WHERE model = %s", (MODEL,))

    # ------------------------------------------------------------------
    # 4) ข้อมูลจริง + คอลัมน์ที่ค้างบนใบรับชำระ
    # ------------------------------------------------------------------
    cr.execute("DROP TABLE IF EXISTS %s CASCADE" % TABLE)
    for column in LEGACY_PAYMENT_COLUMNS:
        cr.execute("ALTER TABLE account_payment DROP COLUMN IF EXISTS %s" % column)

    # ------------------------------------------------------------------
    # 5) sequence + ค่าตั้งค่าเดิมที่ไม่ใช้แล้ว
    # ------------------------------------------------------------------
    cr.execute("DELETE FROM ir_sequence WHERE code = %s", (MODEL,))
    cr.execute("DELETE FROM ir_config_parameter WHERE key IN %s", (LEGACY_PARAMS,))

    _logger.info("npd_scb_auto_payment: ล้างระบบ webhook เดิม (%s) เรียบร้อย", MODEL)
