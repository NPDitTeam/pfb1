# ล้างแท็ก HTML ของข้อมูลเดิม หลังเปลี่ยนฟิลด์ note จาก Html เป็น Text
# แปลงเป็นข้อความล้วนด้วย html2plaintext (ตัวเดียวกับที่ใช้ใน onchange)
# ครอบคลุมทั้ง sale.order.note และ account.move.narration (หมายเหตุที่ไหลไปใบแจ้งหนี้)
import logging
import re

from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

# ตรวจว่ามี "แท็กจริง" หรือไม่ (ต้องเป็นตัวอักษร/ '/' ตามหลัง '<' ทันที)
# กันไม่ให้ไปยุ่งกับข้อความล้วนที่บังเอิญมี < > เช่น "a < b > c" หรือ "<3"
_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")


def _strip_html(cr, table, column):
    cr.execute(
        "SELECT id, {col} FROM {tbl} "
        "WHERE {col} IS NOT NULL AND {col} LIKE %s".format(col=column, tbl=table),
        ("%<%>%",),
    )
    count = 0
    for rec_id, value in cr.fetchall():
        if value and _TAG_RE.search(value):
            plain = html2plaintext(value)
            cr.execute(
                "UPDATE {tbl} SET {col} = %s WHERE id = %s".format(col=column, tbl=table),
                (plain, rec_id),
            )
            count += 1
    _logger.info(
        "sale_order_note_template: cleaned HTML in %s.%s (%s rows)", table, column, count
    )


def migrate(cr, version):
    # ติดตั้งใหม่ (version ว่าง) ไม่มีข้อมูลเก่าให้แปลง
    if not version:
        return
    _strip_html(cr, "sale_order", "note")
    _strip_html(cr, "account_move", "narration")
