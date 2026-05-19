# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_sync_date_order_from_rent(self):
        records = self.filtered(lambda r: r.start_rent_date)
        if not records:
            raise UserError(_("ไม่พบ 'วันที่เริ่มต้นการเช่า' ในรายการที่เลือก"))

        ids = records.ids

        # 1) วันที่สั่งซื้อ (date_order) = วันที่เริ่มต้นการเช่า (คงเวลาเดิมไว้)
        self.env.cr.execute(
            """
            UPDATE sale_order
               SET date_order = (start_rent_date + date_order::time)::timestamp
             WHERE id IN %s
               AND start_rent_date IS NOT NULL
            """,
            (tuple(ids),),
        )
        self.invalidate_cache(fnames=['date_order'], ids=ids)

        # 2) วันที่ใบแจ้งหนี้ (invoice_date) และวันที่กำหนดจ่าย (invoice_date_due)
        #    ของใบแจ้งหนี้ที่ผูกกับใบสั่งขาย ให้เป็นวันเดียวกับวันที่สั่งซื้อ
        #    (= start_rent_date) เฉพาะใบแจ้งหนี้สถานะ "ฉบับร่าง" เท่านั้น
        #    เพื่อไม่ให้กระทบสมุดบัญชีของใบแจ้งหนี้ที่ลงบัญชีแล้ว
        for order in records:
            draft_invoices = order.invoice_ids.filtered(
                lambda m: m.state == 'draft'
            )
            if not draft_invoices:
                continue
            self.env.cr.execute(
                """
                UPDATE account_move
                   SET invoice_date = %s,
                       invoice_date_due = %s
                 WHERE id IN %s
                """,
                (order.start_rent_date, order.start_rent_date,
                 tuple(draft_invoices.ids)),
            )
            draft_invoices.invalidate_cache(
                fnames=['invoice_date', 'invoice_date_due'],
                ids=draft_invoices.ids,
            )

        return True
