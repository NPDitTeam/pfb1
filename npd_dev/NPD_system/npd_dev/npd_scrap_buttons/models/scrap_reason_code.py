# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ScrapReasonCode(models.Model):
    _inherit = 'scrap.reason.code'

    is_damage_repair = fields.Boolean(
        string='ต้องส่งซ่อม',
        help='ถ้าเปิดไว้ เมื่อสร้าง Scrap ด้วย Reason Code นี้ '
             'เอกสารจะเข้าสถานะ "รอดำเนินการแจ้งซ่อม" แทน "เสร็จสิ้น"'
    )

    def _ensure_scrap_location(self):
        """คลังปลายทางของ Reason Code ต้องติ๊ก "Is a Scrap Location?"

        stock.move.scrapped เป็นฟิลด์ related แบบ stored:
            scrapped = related('location_dest_id.scrap_location', store=True)
        และปุ่ม "Scraps" บนใบโอนย้าย/ใบคืน ซ่อนตาม has_scrap_move ซึ่งนับเฉพาะ
        move ที่ scrapped = True ถ้าคลังปลายทางไม่ได้ติ๊กไว้ ปุ่มจะไม่โผล่
        (เคยเจอกับคลัง 'สินค้าชำรุด' ที่ไม่ได้ติ๊ก ทำให้ปุ่มขึ้นเฉพาะสินค้าหาย)

        นอกจากนี้ domain ของ stock.scrap.scrap_location_id ก็บังคับ
        scrap_location = True อยู่แล้ว การติ๊กจึงตรงกับที่ Odoo คาดหวัง
        """
        for rec in self:
            location = rec.location_id
            if location and not location.scrap_location:
                location.sudo().write({'scrap_location': True})

    @api.model
    def create(self, vals):
        record = super().create(vals)
        record._ensure_scrap_location()
        return record

    def write(self, vals):
        res = super().write(vals)
        if 'location_id' in vals:
            self._ensure_scrap_location()
        return res
