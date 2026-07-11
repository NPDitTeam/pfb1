# -*- coding: utf-8 -*-
import logging
from odoo import _, models

_logger = logging.getLogger(__name__)

# ปรับยอดใบสั่งขายให้ตรงใบเสนอราคาเฉพาะเมื่อส่วนต่าง ≤ ค่านี้ (บาท)
# เจตนา: กลบเฉพาะ drift จากการปัดเศษ (เช่น 0.10) ที่เกิดตอน copy → recompute
# ถ้าต่างเกินนี้ = น่าจะมีการแก้รายการจริง → ไม่กลบ (แค่ log + แจ้งใน chatter)
LOCK_TOLERANCE = 1.0


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_convert_to_order(self):
        """ยึดยอดใบสั่งขายให้ตรงกับ 'ใบเสนอราคาครั้งแรก'

        sale_isolated_quotation.action_convert_to_order ใช้ self.copy() สร้าง
        ใบสั่งขายใหม่ → npd_rent_price_round.copy() เรียก _npd_recalc_amounts
        คำนวณ VAT ใหม่ด้วยสูตรปัจจุบัน → ยอดอาจ drift จากใบเสนอราคาที่ frozen
        ไว้ (เช่น 0.10 บาท) แต่ลูกค้าได้ยอดใบเสนอราคาไปแล้ว จึงต้องยึดยอดนั้น
        """
        self.ensure_one()
        # snapshot ยอดใบเสนอราคา (self) 'ก่อน' super — ค่านี้คือยอดที่ลูกค้าได้ไป
        # (self ไม่ถูก copy แตะ แต่เก็บไว้ก่อนกัน edge case ใดๆ ระหว่าง super)
        quote_amounts = {
            'untaxed': self.amount_untaxed,
            'tax': self.amount_tax,
            'total': self.amount_total,
        }
        quote_lines = [
            {
                'product_id': line.product_id.id,
                'price_subtotal': line.price_subtotal,
                'price_total': line.price_total,
                'price_tax': line.price_tax,
            }
            for line in self.order_line.sorted(lambda l: (l.sequence, l.id))
        ]

        res = super().action_convert_to_order()

        order = self.order_id
        if order:
            order._npd_lock_total_to_quotation(self, quote_amounts, quote_lines)
        return res

    def _npd_lock_total_to_quotation(self, quote, quote_amounts, quote_lines):
        """freeze ยอดใบสั่งขาย (self) ให้เท่าใบเสนอราคา — เฉพาะ drift ≤ tolerance

        เขียนยอดผ่าน SQL ตรงๆ (แบบเดียวกับ npd_rent_price_round) เพราะ
        amount_* / price_* เป็น stored computed field ที่ ORM write อาจเมิน
        ต้อง freeze 'ทั้งบรรทัดและหัว' ไม่งั้น _amount_all จะคำนวณหัวกลับจาก
        SUM(line.price_tax) ของบรรทัดที่ยัง drift อยู่
        """
        self.ensure_one()
        diff = round(quote_amounts['total'] - self.amount_total, 2)

        if diff == 0.0:
            return  # ยอดตรงอยู่แล้ว ไม่ต้องทำอะไร

        if abs(diff) > LOCK_TOLERANCE:
            # ต่างเกินเพดาน → อาจมีการแก้รายการจริง ไม่กลบยอด แค่แจ้งเตือน
            msg = _(
                "⚠️ ยอดใบสั่งขายต่างจากใบเสนอราคา %(q)s เกิน %(tol).2f บาท "
                "(ใบเสนอราคา %(qt).2f / คำนวณใหม่ %(ot).2f = ต่าง %(d).2f) "
                "— ไม่ล็อกยอดอัตโนมัติ กรุณาตรวจสอบรายการ"
            ) % {'q': quote.name, 'tol': LOCK_TOLERANCE,
                 'qt': quote_amounts['total'], 'ot': self.amount_total,
                 'd': diff}
            _logger.warning(msg)
            self.message_post(body=msg)
            return

        order_total_before = self.amount_total
        cr = self.env.cr

        # จับคู่บรรทัดใบสั่งขาย (copy) กับ snapshot ใบเสนอราคา ตามลำดับ (sequence, id)
        # — copy รักษาลำดับบรรทัด จึง zip ตรงกัน + เช็ค product กันจับคู่เพี้ยน
        order_lines = self.order_line.sorted(lambda l: (l.sequence, l.id))
        if len(order_lines) == len(quote_lines):
            for oline, qv in zip(order_lines, quote_lines):
                if oline.product_id.id != qv['product_id']:
                    continue
                cr.execute(
                    "UPDATE sale_order_line "
                    "SET price_subtotal = %s, price_total = %s, price_tax = %s "
                    "WHERE id = %s",
                    (qv['price_subtotal'], qv['price_total'],
                     qv['price_tax'], oline.id),
                )
        else:
            _logger.warning(
                "npd_quote_total_lock: จำนวนบรรทัดไม่ตรง order %s (%d) vs "
                "quote %s (%d) — freeze เฉพาะหัวเอกสาร",
                self.name, len(order_lines), quote.name, len(quote_lines),
            )

        # หัวเอกสารใบสั่งขาย = ยอดใบเสนอราคา
        cr.execute(
            "UPDATE sale_order "
            "SET amount_untaxed = %s, amount_tax = %s, amount_total = %s "
            "WHERE id = %s",
            (quote_amounts['untaxed'], quote_amounts['tax'],
             quote_amounts['total'], self.id),
        )
        self.invalidate_cache(
            ['amount_untaxed', 'amount_tax', 'amount_total'], [self.id])
        self.order_line.invalidate_cache(
            ['price_subtotal', 'price_total', 'price_tax'])

        self.message_post(body=_(
            "🔒 ล็อกยอดตามใบเสนอราคา %(q)s: คำนวณใหม่ได้ %(o).2f → "
            "ยึดยอดใบเสนอราคา %(qt).2f (ปรับ %(d).2f บาท)"
        ) % {'q': quote.name, 'o': order_total_before,
             'qt': quote_amounts['total'], 'd': diff})
