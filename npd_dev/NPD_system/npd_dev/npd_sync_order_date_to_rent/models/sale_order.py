# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_sync_date_order_from_rent(self):
        ids = [r.id for r in self if r.start_rent_date]
        if not ids:
            raise UserError(_("ไม่พบ 'วันที่เริ่มต้นการเช่า' ในรายการที่เลือก"))

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
        return True
