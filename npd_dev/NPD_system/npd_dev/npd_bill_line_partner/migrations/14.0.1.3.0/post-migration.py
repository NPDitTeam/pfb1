# -*- coding: utf-8 -*-
"""บิลเก่าของผู้ขายที่ต้องระบุ Partner รายบรรทัด (ธนาคารกสิกรไทย): Tax Invoice ที่ยังเป็นชื่อผู้ขาย
และยังไม่มี Partner รายบรรทัด ให้เป็นค่าว่าง (ผู้ใช้สั่ง: Partner ต้องมาจากรายการจากใบแจ้งหนี้เท่านั้น)
เก็บค่าเดิมไว้ในตาราง npd_blp_taxinv_partner_backup เผื่อย้อนกลับ"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        CREATE TABLE IF NOT EXISTS npd_blp_taxinv_partner_backup (
            tax_invoice_id integer PRIMARY KEY,
            move_id integer,
            partner_id integer,
            cleared_at timestamp DEFAULT now()
        )""")
    cr.execute("""
        WITH target AS (
            SELECT t.id, t.move_id, t.partner_id
            FROM account_move_tax_invoice t
            JOIN account_move m ON m.id = t.move_id
            JOIN res_partner v ON v.id = m.partner_id
            JOIN res_partner tp ON tp.id = t.partner_id
            WHERE m.move_type IN ('in_invoice', 'in_refund', 'in_receipt')
              AND (v.name LIKE '%%ธนาคารกสิกรไทย%%' OR v.npd_require_line_partner
                   OR regexp_replace(coalesce(v.vat, ''), '[^0-9]', '', 'g') = '0107536000315')
              AND coalesce(tp.commercial_partner_id, tp.id) = coalesce(v.commercial_partner_id, v.id)
              AND NOT EXISTS (SELECT 1 FROM account_move_line l
                              WHERE l.move_id = m.id AND l.npd_line_partner_id IS NOT NULL)
        ), saved AS (
            INSERT INTO npd_blp_taxinv_partner_backup (tax_invoice_id, move_id, partner_id)
            SELECT id, move_id, partner_id FROM target
            ON CONFLICT (tax_invoice_id) DO NOTHING
        )
        UPDATE account_move_tax_invoice t SET partner_id = NULL
        FROM target WHERE t.id = target.id
    """)
    _logger.info('npd_bill_line_partner: ล้าง Partner (ชื่อผู้ขาย) ใน Tax Invoice บิลเก่า %s แถว', cr.rowcount)
