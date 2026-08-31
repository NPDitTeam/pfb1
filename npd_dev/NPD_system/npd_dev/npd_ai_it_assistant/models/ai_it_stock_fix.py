# -*- coding: utf-8 -*-
"""หัวข้อที่ 1 : แก้ปัญหาตัดสต็อกไม่ได้เนื่องจากสต็อกไม่พอ

ไฟล์นี้เก็บ "ตรรกะจริง" ที่แตะฐานข้อมูลไว้ที่เดียว เพื่อให้ตรวจทานง่าย:

  * SQL ทั้งหมดเขียนไว้ล่วงหน้าเป็นค่าคงที่ (SQL_*) และรับค่าผ่าน parameter
    เท่านั้น — AI ไม่ได้เป็นคนสร้าง SQL และไม่มีทางแทรกคำสั่งเข้ามาได้
  * เติมสต๊อกได้อย่างเดียว (diff > 0) ไม่มีเส้นทางไหนที่ลดสต๊อก
  * เขียนลง location ของ "สาขาที่พนักงานสังกัด" เท่านั้น

พฤติกรรมอิงกับปุ่ม "ตัดสต็อก Auto 🚚" เดิม (so_auto_stock_cut):
วิธีหาคลังต้นทางของสาขา และการเติมสต๊อกให้ถึงจำนวนสต๊อกจริงที่พนักงานนับได้
ใช้กติกาเดียวกัน เพื่อให้กดปุ่มตัดสต๊อกต่อได้ทันทีหลังเติม
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# ==============================================================================
# SQL ที่เตรียมไว้ล่วงหน้า — ห้ามต่อสตริงค่าใด ๆ เข้าไป ใช้ผ่าน parameter เท่านั้น
# ==============================================================================

# ล็อกแถว quant ของ (สินค้า, คลัง) ที่ไม่มี lot/package/owner เพื่อกันสองคนเติมพร้อมกัน
SQL_LOCK_QUANT = """
    SELECT id, quantity
      FROM stock_quant
     WHERE product_id  = %s
       AND location_id = %s
       AND lot_id      IS NULL
       AND package_id  IS NULL
       AND owner_id    IS NULL
     ORDER BY id
     LIMIT 1
     FOR UPDATE
"""

# เติมจำนวนเข้าไปในแถวเดิม (บวกเพิ่ม ไม่ใช่ทับค่า เพื่อไม่ให้ทับงานของคนอื่น)
SQL_ADD_QTY = """
    UPDATE stock_quant
       SET quantity   = quantity + %s,
           in_date    = COALESCE(in_date, (now() AT TIME ZONE 'UTC')),
           write_uid  = %s,
           write_date = (now() AT TIME ZONE 'UTC')
     WHERE id = %s
"""

# ยังไม่เคยมี quant ของสินค้านี้ในคลังนี้ -> สร้างแถวใหม่
SQL_INSERT_QUANT = """
    INSERT INTO stock_quant
           (product_id, location_id, company_id, quantity, reserved_quantity,
            in_date,
            create_uid, create_date, write_uid, write_date)
    VALUES (%s, %s, %s, %s, 0.0,
            (now() AT TIME ZONE 'UTC'),
            %s, (now() AT TIME ZONE 'UTC'), %s, (now() AT TIME ZONE 'UTC'))
 RETURNING id
"""

# อ่านยอดรวมหลังเติม ไว้ยืนยันผลให้พนักงานเห็น
SQL_SUM_QTY = """
    SELECT COALESCE(SUM(quantity), 0.0)
      FROM stock_quant
     WHERE product_id  = %s
       AND location_id = %s
"""


class NpdAiItStockFix(models.AbstractModel):
    _name = 'npd.ai.it.stock.fix'
    _description = 'ตัวช่วย AI-IT : แก้ปัญหาสต็อกไม่พอสำหรับตัดสต๊อก'

    # ------------------------------------------------------------------
    # หาเอกสาร / สาขา / คลัง
    # ------------------------------------------------------------------
    @api.model
    def find_document(self, doc_number):
        """หาเอกสารจากเลขที่ที่พนักงานพิมพ์มา

        รองรับทั้งเลขใบสั่งขาย และเลขใบจัดส่ง (ใบจัดส่งจะถูกโยงกลับไปหาใบสั่งขาย)
        คืน (record, error_message) — record เป็น sale.order หรือ stock.picking
        """
        doc_number = (doc_number or '').strip()
        if not doc_number:
            return None, None

        order = self.env['sale.order'].sudo().search(
            [('name', '=', doc_number)], limit=1)
        if order:
            return order, None

        picking = self.env['stock.picking'].sudo().search(
            [('name', '=', doc_number)], limit=1)
        if picking:
            if picking.sale_id:
                return picking.sale_id, None
            return picking, None

        return None, 'ไม่พบเอกสารเลขที่ "%s" ในระบบ' % doc_number

    @api.model
    def user_allowed_branches(self, user=None):
        """สาขาที่พนักงานคนนี้สังกัด (สาขาปัจจุบัน + สาขาที่อนุญาต)"""
        user = user or self.env.user
        return user.sudo().branch_id | user.sudo().branch_ids

    @api.model
    def resolve_branch(self, document, user=None):
        """สาขาที่จะใช้ทำงาน + ข้อความ error ถ้าไม่มีสิทธิ์

        ยึด "สาขาที่พนักงานสังกัด" เป็นกำแพงเสมอ: ถ้าเอกสารเป็นของสาขาอื่น
        จะไม่ยอมให้แก้ เพื่อกันการเติมสต๊อกข้ามสาขา
        """
        user = user or self.env.user
        allowed = self.user_allowed_branches(user)
        if not allowed:
            return None, ('บัญชีผู้ใช้ของคุณยังไม่ได้ระบุสาขา '
                          'กรุณาแจ้งฝ่าย IT ให้ตั้งค่าสาขาก่อนใช้งานเมนูนี้')

        doc_branch = document.sudo().branch_id if 'branch_id' in document._fields else False
        if doc_branch:
            if doc_branch not in allowed:
                return None, ('เอกสารนี้เป็นของสาขา "%s" ซึ่งไม่ใช่สาขาที่คุณสังกัด '
                              'จึงไม่สามารถแก้ไขสต๊อกให้ได้' % doc_branch.name)
            return doc_branch, None

        # เอกสารไม่ได้ระบุสาขา -> ใช้สาขาปัจจุบันของพนักงาน
        return (user.sudo().branch_id or allowed[0]), None

    @api.model
    def get_branch_internal_location(self, branch, product_ids=None):
        """หาคลังต้นทาง (usage=internal) ของสาขา

        ใช้กติกาเดียวกับปุ่ม "ตัดสต็อก Auto" เดิม: บางสาขามี location ซ้ำชื่อกัน
        ถ้าหยิบ limit=1 มั่ว ๆ จะได้คลังเปล่าแล้วจองของไม่ได้ จึงเลือกคลังที่
        "มีสต๊อกจริง" ของสินค้าที่จะตัดมากที่สุด
        """
        Location = self.env['stock.location'].sudo()
        locations = Location.search([
            ('branch_id', '=', branch.id),
            ('usage', '=', 'internal'),
        ])
        if len(locations) <= 1:
            return locations[:1]

        Quant = self.env['stock.quant'].sudo()

        def _best(domain):
            agg = {}
            for quant in Quant.search(domain):
                agg[quant.location_id.id] = agg.get(quant.location_id.id, 0.0) + quant.quantity
            if agg:
                best_id = max(agg, key=agg.get)
                if agg[best_id] > 0:
                    return Location.browse(best_id)
            return None

        if product_ids:
            location = _best([('location_id', 'in', locations.ids),
                              ('product_id', 'in', list(product_ids))])
            if location:
                return location
        location = _best([('location_id', 'in', locations.ids)])
        if location:
            return location
        return locations[:1]

    # ------------------------------------------------------------------
    # อ่านความต้องการ / สต๊อกคงเหลือ
    # ------------------------------------------------------------------
    @api.model
    def get_location_qty(self, product, location):
        """สต๊อกคงเหลือของสินค้าในคลังนี้ (อ่านแบบเดียวกับที่ปุ่มตัดสต๊อกใช้)"""
        return product.sudo().with_context(location=location.id).qty_available

    @api.model
    def _required_lines(self, document):
        """คืน [(product, qty_ที่ต้องใช้)] จากเอกสาร"""
        result = []
        if document._name == 'sale.order':
            lines = document.sudo().order_line.filtered(
                lambda l: not l.display_type
                and l.product_id
                and l.product_id.type in ('product', 'consu')
            )
            for line in lines:
                # pfb_quantity = "จํานวนสินค้า" ที่ระบบตัดสต๊อกจริงใช้ (npd_all_customs)
                # ถ้าโมดูลนั้นไม่ได้ติดตั้ง หรือยังไม่ได้กรอก ให้ถอยไปใช้จำนวนขายปกติ
                qty = 0.0
                if 'pfb_quantity' in line._fields:
                    qty = float(line.pfb_quantity or 0.0)
                if qty <= 0:
                    qty = float(line.product_uom_qty or 0.0)
                if qty > 0:
                    result.append((line.product_id, qty))
        else:  # stock.picking
            for move in document.sudo().move_ids_without_package:
                if move.state in ('done', 'cancel') or not move.product_id:
                    continue
                qty = float(move.product_uom_qty or 0.0)
                if qty > 0:
                    result.append((move.product_id, qty))
        return result

    @api.model
    def analyze(self, document, location):
        """เทียบ "ต้องใช้" กับ "คงเหลือในคลังสาขา" แล้วคืนรายการที่ไม่พอ

        คืน (all_items, shortage_items) — แต่ละ item เป็น dict ที่ serialize
        ลง session ได้ (เก็บเป็น JSON)
        """
        need_by_product = {}
        products = {}
        for product, qty in self._required_lines(document):
            need_by_product[product.id] = need_by_product.get(product.id, 0.0) + qty
            products[product.id] = product

        all_items, shortage_items = [], []
        for product_id, need in need_by_product.items():
            product = products[product_id]
            current = self.get_location_qty(product, location)
            item = {
                'product_id': product_id,
                'name': product.display_name,
                'code': product.default_code or '',
                'uom': product.uom_id.name or '',
                'need': need,
                'current': current,
                'missing': max(need - current, 0.0),
                'target': None,   # จำนวนสต๊อกจริงที่พนักงานจะแจ้งเข้ามา
            }
            all_items.append(item)
            if item['missing'] > 0:
                shortage_items.append(item)

        all_items.sort(key=lambda i: i['name'])
        shortage_items.sort(key=lambda i: i['name'])
        return all_items, shortage_items

    # ------------------------------------------------------------------
    # เติมสต๊อก (SQL ที่เตรียมไว้ล่วงหน้า)
    # ------------------------------------------------------------------
    @api.model
    def apply_topup(self, location, items):
        """เติมสต๊อกให้ถึงจำนวนสต๊อกจริงที่พนักงานแจ้ง

        items: list ของ dict ที่มี product_id และ target (จำนวนสต๊อกจริง)
        คืน list ผลลัพธ์ต่อสินค้า [{product_id, name, before, added, after}]

        หมายเหตุความปลอดภัย: เติมเฉพาะเมื่อ target > สต๊อกปัจจุบัน เท่านั้น
        ไม่มีเส้นทางที่ลดสต๊อก แม้พนักงานจะแจ้งตัวเลขต่ำกว่าของจริง
        """
        Product = self.env['product.product'].sudo()
        company_id = (location.company_id.id
                      or self.env.company.id
                      or self.env.user.company_id.id)
        uid = self.env.uid
        applied = []

        # กำลังจะยิง SQL ตรงไปที่ตาราง ต้องดันค่าที่ ORM ค้างอยู่ลง DB ก่อน
        self.env['stock.quant'].flush()

        for item in items:
            product = Product.browse(item['product_id'])
            if not product.exists():
                continue
            target = float(item.get('target') or 0.0)
            before = self.get_location_qty(product, location)
            diff = target - before
            if diff <= 0:
                # สต๊อกพอแล้ว (อาจมีคนอื่นเติมไปก่อนหน้า) — ไม่ต้องแตะ
                applied.append({
                    'product_id': product.id,
                    'name': product.display_name,
                    'before': before,
                    'added': 0.0,
                    'after': before,
                })
                continue

            self.env.cr.execute(SQL_LOCK_QUANT, (product.id, location.id))
            row = self.env.cr.fetchone()
            if row:
                self.env.cr.execute(SQL_ADD_QTY, (diff, uid, row[0]))
            else:
                self.env.cr.execute(
                    SQL_INSERT_QUANT,
                    (product.id, location.id, company_id, diff, uid, uid),
                )

            self.env.cr.execute(SQL_SUM_QTY, (product.id, location.id))
            after = self.env.cr.fetchone()[0] or 0.0

            _logger.info(
                'ตัวช่วย AI-IT: เติมสต๊อก %s @ %s | %.2f -> %.2f (+%.2f) โดย uid=%s',
                product.display_name, location.complete_name, before, after, diff, uid,
            )
            applied.append({
                'product_id': product.id,
                'name': product.display_name,
                'before': before,
                'added': diff,
                'after': after,
            })

        # แก้ด้วย SQL ตรง ๆ ORM จึงยังจำค่าเก่าอยู่ ต้องล้าง cache เอง
        if applied:
            self.env['stock.quant'].invalidate_cache()
            Product.invalidate_cache(
                ['qty_available', 'virtual_available', 'free_qty'],
                [i['product_id'] for i in applied],
            )
        return applied
