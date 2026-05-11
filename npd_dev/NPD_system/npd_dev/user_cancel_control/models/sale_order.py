# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_draft(self):
        """ยกเลิกใบสั่งขายเป็นร่าง"""
        if not self.env.user.allow_cancel:
            raise UserError(
                'คุณไม่ได้รับอนุญาตให้ยกเลิกใบสั่งขายนี้ '
                'กรุณาติดต่อผู้ดูแลระบบ'
            )
        return super(SaleOrder, self).action_draft()

    def action_cancel(self):
        """ยกเลิกใบสั่งขาย"""
        if not self.env.user.allow_cancel:
            raise UserError(
                'คุณไม่ได้รับอนุญาตให้ยกเลิกใบสั่งขายนี้ '
                'กรุณาติดต่อผู้ดูแลระบบ'
            )
        return super(SaleOrder, self).action_cancel()
