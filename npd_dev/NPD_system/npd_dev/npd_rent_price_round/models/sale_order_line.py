import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    use_new_calc = fields.Boolean(
        related='order_id.use_new_calc',
        store=True,
        readonly=True,
    )

    use_baan_kheaw = fields.Boolean(
        related='order_id.use_baan_kheaw',
        store=True,
        readonly=True,
    )

    vat_from_total = fields.Boolean(
        related='order_id.vat_from_total',
        store=True,
        readonly=True,
    )

    price_unit_no_vat = fields.Float(
        string='ราคาต่อหน่วย (ถอด VAT)',
        compute='_compute_price_unit_no_vat',
        inverse='_inverse_price_unit_no_vat',
        store=False,
        digits=(16, 2),
    )

    @api.depends('price_unit', 'tax_id',
                 'order_id.use_new_calc', 'order_id.use_baan_kheaw')
    def _compute_price_unit_no_vat(self):
        """ราคาต่อหน่วย ex-VAT
        อ่าน flag จาก order_id ตรงๆ ไม่ผ่าน related cache
        เพื่อให้ใน onchange context ได้ค่าล่าสุดของ form"""
        for line in self:
            order = line.order_id
            use_new_calc = order.use_new_calc if order else False
            use_baan_kheaw = order.use_baan_kheaw if order else False
            has_vat_7_incl = bool(line.tax_id) and any(
                t.price_include and abs(t.amount - 7.0) < 0.01
                for t in line.tax_id
            )
            if use_new_calc and has_vat_7_incl and not use_baan_kheaw:
                line.price_unit_no_vat = round(line.price_unit / 1.07, 2)
            else:
                line.price_unit_no_vat = line.price_unit

    def _inverse_price_unit_no_vat(self):
        """User แก้ค่าในตาราง → กลับไปอัพเดต price_unit
        อ่าน flag จาก order_id ตรงๆ เพื่อกัน stale related cache
        ข้าม write-back ถ้าค่าใหม่ตรงกับ compute ของ price_unit เดิม
        (เกิดจาก flag toggle ไม่ใช่ user แก้เอง — กัน round-trip drift)"""
        for line in self:
            order = line.order_id
            use_new_calc = order.use_new_calc if order else False
            use_baan_kheaw = order.use_baan_kheaw if order else False
            has_vat_7_incl = bool(line.tax_id) and any(
                t.price_include and abs(t.amount - 7.0) < 0.01
                for t in line.tax_id
            )
            if use_new_calc and has_vat_7_incl and not use_baan_kheaw:
                expected = round(line.price_unit / 1.07, 2)
                if abs(line.price_unit_no_vat - expected) < 0.001:
                    continue
                new_price_unit = round(line.price_unit_no_vat * 1.07, 2)
            else:
                if abs(line.price_unit_no_vat - line.price_unit) < 0.001:
                    continue
                new_price_unit = line.price_unit_no_vat
            if abs(line.price_unit - new_price_unit) > 0.001:
                line.price_unit = new_price_unit

    @api.onchange('price_unit_no_vat')
    def _onchange_price_unit_no_vat(self):
        # sync price_unit ทันทีในฟอร์มเมื่อ user แก้ค่าในตาราง
        # อ่าน flag จาก order_id ตรงๆ เพื่อกัน stale related cache
        # ข้าม write-back ถ้าค่าใหม่ตรงกับ compute ของ price_unit เดิม
        # (เกิดจาก flag toggle ไม่ใช่ user แก้เอง — กัน round-trip drift)
        for line in self:
            order = line.order_id
            use_new_calc = order.use_new_calc if order else False
            use_baan_kheaw = order.use_baan_kheaw if order else False
            has_vat_7_incl = bool(line.tax_id) and any(
                t.price_include and abs(t.amount - 7.0) < 0.01
                for t in line.tax_id
            )
            if use_new_calc and has_vat_7_incl and not use_baan_kheaw:
                expected = round(line.price_unit / 1.07, 2)
                if abs(line.price_unit_no_vat - expected) < 0.001:
                    continue
                new_price_unit = round(line.price_unit_no_vat * 1.07, 2)
            else:
                if abs(line.price_unit_no_vat - line.price_unit) < 0.001:
                    continue
                new_price_unit = line.price_unit_no_vat
            if line.price_unit != new_price_unit:
                line.price_unit = new_price_unit

    def _npd_compute_method_a(self):
        """Method A: subtotal = round(price_unit / 1.07, 2) × qty
        ราคาแสดง × qty = รวม (สอดคล้องสายตา)
        ข้าม line ที่ price_unit = 0 (free/promo) เพื่อป้องกันค่าเพี้ยน
        ข้าม order ที่ติ๊ก use_baan_kheaw (ใช้ราคาบ้านเขียวตรงๆ)
        """
        result = {}
        for line in self:
            if not line.use_new_calc:
                continue
            if line.use_baan_kheaw:
                continue
            if not line.price_unit or not line.product_uom_qty or not line.tax_id:
                continue
            has_vat_7_incl = any(
                t.price_include and abs(t.amount - 7.0) < 0.01
                for t in line.tax_id
            )
            if not has_vat_7_incl:
                continue
            unit_ex_vat = round(line.price_unit / 1.07, 2)
            new_subtotal = round(unit_ex_vat * line.product_uom_qty, 2)
            new_tax = round(new_subtotal * 0.07, 2)
            new_price_total = round(new_subtotal + new_tax, 2)
            result[line.id] = (new_subtotal, new_price_total, new_tax)
        return result

    def _npd_force_round_sql(self):
        rounded = self._npd_compute_method_a()
        if not rounded:
            # ถ้าไม่มีอะไรต้อง force-round แต่อาจมี order ที่ติ๊ก use_baan_kheaw
            # ต้อง sync amount_total ของ order ตามผลคำนวณ default ของ Odoo
            self._npd_sync_baan_kheaw_orders()
            return
        cr = self.env.cr
        for line_id, (new_subtotal, new_total, new_tax) in rounded.items():
            cr.execute(
                """
                UPDATE sale_order_line
                SET price_subtotal = %s,
                    price_total = %s,
                    price_tax = %s
                WHERE id = %s
                """,
                (new_subtotal, new_total, new_tax, line_id),
            )
        line_ids = list(rounded.keys())
        cr.execute(
            "SELECT DISTINCT order_id FROM sale_order_line WHERE id IN %s",
            (tuple(line_ids),),
        )
        order_ids = [row[0] for row in cr.fetchall()]
        for order_id in order_ids:
            cr.execute(
                """
                SELECT
                    COALESCE(SUM(price_subtotal), 0) AS untaxed,
                    COALESCE(SUM(price_tax), 0) AS tax
                FROM sale_order_line
                WHERE order_id = %s
                """,
                (order_id,),
            )
            untaxed, tax = cr.fetchone()
            untaxed = round(float(untaxed or 0), 2)
            tax = round(float(tax or 0), 2)
            # Method B: ถ้าติ๊ก vat_from_total → คิด VAT จากยอดรวม
            # ปัดครั้งเดียว แทนที่ผลรวมของ price_tax ที่ปัดรายบรรทัด
            order = self.env['sale.order'].browse(order_id)
            if order.vat_from_total:
                tax = round(untaxed * 0.07, 2)
            total = round(untaxed + tax, 2)
            cr.execute(
                """
                UPDATE sale_order
                SET amount_untaxed = %s,
                    amount_tax = %s,
                    amount_total = %s
                WHERE id = %s
                """,
                (untaxed, tax, total, order_id),
            )
        # Sync orders ที่ติ๊ก use_baan_kheaw แยก (ไม่ผ่าน method A)
        self._npd_sync_baan_kheaw_orders()
        self.env.cache.invalidate()

    def _npd_sync_baan_kheaw_orders(self):
        """อัพเดท amount_untaxed/tax/total ของ order ที่ติ๊ก use_baan_kheaw
        จากผลรวม sale_order_line ตามที่ Odoo คำนวณตามปกติ"""
        if not self:
            return
        baan_kheaw_orders = self.mapped('order_id').filtered('use_baan_kheaw')
        if not baan_kheaw_orders:
            return
        cr = self.env.cr
        for order in baan_kheaw_orders:
            cr.execute(
                """
                SELECT
                    COALESCE(SUM(price_subtotal), 0) AS untaxed,
                    COALESCE(SUM(price_tax), 0) AS tax
                FROM sale_order_line
                WHERE order_id = %s
                """,
                (order.id,),
            )
            untaxed, tax = cr.fetchone()
            untaxed = round(float(untaxed or 0), 2)
            tax = round(float(tax or 0), 2)
            # Method B: VAT จากยอดรวม ปัดครั้งเดียว
            if order.vat_from_total:
                tax = round(untaxed * 0.07, 2)
            total = round(untaxed + tax, 2)
            cr.execute(
                """
                UPDATE sale_order
                SET amount_untaxed = %s,
                    amount_tax = %s,
                    amount_total = %s
                WHERE id = %s
                """,
                (untaxed, tax, total, order.id),
            )

    def _npd_recalc_amounts(self):
        """ใช้สำหรับเรียกซ้ำเมื่อ flag use_new_calc/use_baan_kheaw เปลี่ยน
        เพื่อ rebuild ยอดทั้ง order"""
        if not self:
            return
        # invalidate cache แล้วบังคับ recompute _compute_amount ของทุก line
        self.invalidate_cache(['price_subtotal', 'price_total', 'price_tax',
                               'use_new_calc', 'use_baan_kheaw',
                               'vat_from_total'])
        self._compute_amount()
        # บังคับ flush ค่าใหม่จาก memory ลง DB ก่อน SQL select ใน
        # _npd_force_round_sql / _npd_sync_baan_kheaw_orders ไม่งั้น
        # SUM(price_subtotal) จะดึงค่าเก่า → ยอด order ไม่กลับเป็นสูตรใหม่
        self.flush()
        # แล้วเขียนยอดผ่าน SQL (ทั้ง method A และ baan_kheaw sync)
        self._npd_force_round_sql()

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id',
                 'discount_method', 'discount_amount', 'use_new_calc',
                 'use_baan_kheaw')
    def _compute_amount(self):
        res = super()._compute_amount()
        rounded = self._npd_compute_method_a()
        for line in self:
            if line.id in rounded:
                new_subtotal, new_total, new_tax = rounded[line.id]
                line.price_subtotal = new_subtotal
                line.price_total = new_total
                line.price_tax = new_tax
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._npd_force_round_sql()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if not self._context.get('npd_skip_round'):
            self.with_context(npd_skip_round=True)._npd_force_round_sql()
        return res
