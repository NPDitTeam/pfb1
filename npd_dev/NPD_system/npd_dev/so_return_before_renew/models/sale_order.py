# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def copy(self, default=None):
        """ก่อนกดซ้ำเอกสาร (ต่ออายุบิลเช่า): ตรวจสต๊อกก่อน
        ใช้เฉพาะใบเสนอราคาประเภท 'เช่า' (pfb_so_type == 'rent') เท่านั้น
        ถ้ายังมีการตัดสต๊อกที่ 'ยังไม่ได้คืน' (sc_has_cut = True จากโมดูล so_auto_stock_cut)
        -> บล็อก + แจ้งเตือน ให้กดคืนสต๊อกให้สถานะเสร็จสิ้นก่อน จึงจะต่ออายุได้
        ถ้าคืนเรียบร้อยแล้ว / ไม่เคยตัด / ไม่ใช่ประเภทเช่า -> กดซ้ำทำงานตามปกติ

        หมายเหตุ: เช็คก่อนเรียก super() เพื่อบล็อกก่อนที่ logic ต่ออายุ (deposit_ref ฯลฯ)
        ของโมดูลอื่นจะทำงาน
        """
        is_rent = 'pfb_so_type' in self._fields and self.pfb_so_type == 'rent'
        if is_rent and self.sc_has_cut:
            raise UserError(_(
                "❌ ยังไม่สามารถต่ออายุบิล (กดซ้ำเอกสาร) ได้\n\n"
                "เอกสาร %s ยังมีการตัดสต๊อกที่ 'ยังไม่ได้คืน'\n\n"
                "กรุณากดปุ่ม 'คืนสต๊อก Auto ↩️' ให้สถานะเป็น 'เสร็จสิ้น' ก่อน "
                "จึงจะต่ออายุบิลได้"
            ) % (self.name or ''))
        return super(SaleOrder, self).copy(default)
