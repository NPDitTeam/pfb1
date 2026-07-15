# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

# ----------------------------------------------------------------------------
# เลขที่ใบส่งมอบสินค้า = RDO- + yymmdd + เลขรัน 4 หลัก  เช่น RDO-2607140001
#   - รันจาก ir.sequence code = 'npd.delivery.note'
#   - สร้างครั้งเดียวตอนกดยืนยันใบสั่งขาย (action_confirm) แล้วเก็บไว้ ไม่เปลี่ยนอีก
#   - copy=True : ซ้ำเอกสาร -> ใช้เลขเดิม ไม่รันเลขใหม่ (เหมือนเลขที่สัญญาเช่า)
# ----------------------------------------------------------------------------


class SaleOrder(models.Model):
    _inherit = "sale.order"

    delivery_note_no = fields.Char(
        string=u"เลขที่ใบส่งมอบสินค้า",
        copy=True,  # ซ้ำเอกสารใช้เลขเดิม ไม่รันเลขใหม่
        readonly=True,
        help=u"เลขรันใบส่งมอบสินค้า (RDO-yymmdd+ลำดับ) สร้างอัตโนมัติเมื่อยืนยันใบสั่งขาย",
    )

    def _is_delivery_note_order(self, order):
        """ออกเลขเฉพาะใบขายประเภท 'เช่า' (rent) -- ถ้าไม่มีโมดูล pfb_so_type ให้ออกทุกใบ"""
        if "pfb_so_type" in order._fields:
            return order.pfb_so_type == "rent"
        return True

    def _has_delivery_deposit_ref(self, order):
        """เอกสารนี้อ้างอิงเอกสารก่อนหน้า (deposit_ref มีค่า) = เอกสารต่อเนื่อง/ซ้ำ"""
        if "deposit_ref" not in order._fields:
            return False
        return bool((order.deposit_ref or "").strip())

    def _ensure_delivery_note_no(self):
        """สร้างเลขที่ใบส่งมอบสินค้าให้ครั้งแรก แล้วเก็บไว้ (ไม่เปลี่ยนถ้ามีแล้ว)"""
        seq_obj = self.env["ir.sequence"]
        for order in self:
            if order.delivery_note_no:
                continue
            number = seq_obj.next_by_code("npd.delivery.note")
            if not number:
                raise UserError(
                    u"ไม่พบลำดับเลขที่ใบส่งมอบสินค้า (ir.sequence code = "
                    u"'npd.delivery.note') กรุณาอัปเดตโมดูล "
                    u"pfb_npd_sale_form_delivery_note"
                )
            order.delivery_note_no = number
        return True

    def action_confirm(self):
        """กดยืนยัน -> ออกเลขที่ใบส่งมอบสินค้า (เฉพาะใบขายประเภทเช่า)

        - มีเลขอยู่แล้ว (copy มาจากต้นฉบับ)  -> ใช้เลขเดิม ไม่รันใหม่
        - deposit_ref มีค่า = เอกสารต่อเนื่อง/ซ้ำ แต่ต้นฉบับไม่มีเลข -> ไม่ออกเลขให้
        - deposit_ref ว่าง = เอกสารใหม่                            -> รันเลขใหม่
        """
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if not self._is_delivery_note_order(order):
                continue
            if order.delivery_note_no:
                continue  # มีเลขอยู่แล้ว (copy มาจากต้นฉบับ) -> ใช้เลขเดิม
            if self._has_delivery_deposit_ref(order):
                continue  # เอกสารต่อเนื่องจากต้นฉบับที่ไม่มีเลข -> ไม่สร้างเลข
            order._ensure_delivery_note_no()
        return res
