import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """รีเซ็ต vat_from_total = FALSE ให้กับ SO/Invoice/Receipt ที่มีอยู่ทั้งหมด

    เหตุผล:
    ตอนเพิ่มฟิลด์ vat_from_total (default=True) ใน v14.0.1.0.27 — Odoo's
    `_init_column` backfill ค่า TRUE ให้แถวเก่าทุกแถวอัตโนมัติ
    → เอกสารเก่าทั้งหมดติ๊ก vat_from_total = TRUE โดยไม่ตั้งใจ

    Migration นี้:
    1. รีเซ็ต vat_from_total = FALSE สำหรับทุกแถวที่มีอยู่
    2. หลัง migration → SO/Invoice ใหม่ที่สร้างต่อไปจะใช้ default=True ผ่าน
       Python create() (ปกติ — ไม่กระทบ flow ใหม่)
    3. User สามารถติ๊กกลับเฉพาะใบเก่าที่ต้องการ Method B ภายหลังได้

    Pattern เดียวกับ v14.0.1.0.4 ที่รีเซ็ต use_new_calc = FALSE ตอน
    introduce field นั้น
    """
    if not version:
        return
    _logger.info(
        "[npd_rent_price_round] migrating to 14.0.1.0.31: "
        "resetting vat_from_total = FALSE for all existing records"
    )

    cr.execute("UPDATE sale_order SET vat_from_total = FALSE")
    so_count = cr.rowcount
    cr.execute("UPDATE account_move SET vat_from_total = FALSE")
    move_count = cr.rowcount

    # Sync line tables ด้วย เพราะ related field store=True ไม่ recompute
    # เมื่อ SQL update ตรงๆ บน parent
    cr.execute("""
        UPDATE sale_order_line sol
        SET vat_from_total = so.vat_from_total
        FROM sale_order so
        WHERE sol.order_id = so.id
    """)
    sol_count = cr.rowcount
    cr.execute("""
        UPDATE account_move_line aml
        SET vat_from_total = am.vat_from_total
        FROM account_move am
        WHERE aml.move_id = am.id
    """)
    aml_count = cr.rowcount

    _logger.info(
        "[npd_rent_price_round] reset vat_from_total: "
        "%s sale.order, %s account.move, "
        "%s sale.order.line, %s account.move.line",
        so_count, move_count, sol_count, aml_count,
    )
