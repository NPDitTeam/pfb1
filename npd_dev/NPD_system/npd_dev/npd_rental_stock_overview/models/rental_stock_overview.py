# -*- coding: utf-8 -*-
from odoo import models, fields, tools


class RentalStockOverview(models.Model):
    """รายงานภาพรวมสต็อก เช่า แยกสาขา (เรียลไทม์ผ่าน SQL View)

    เป็น PostgreSQL View (_auto = False) จึงคำนวณ 'สด' จากตารางจริงทุกครั้งที่เปิด
    ไม่ต้องมี cron / ปุ่มรีเฟรช / เก็บข้อมูลซ้ำ

    1 แถว = (สินค้า x สาขา)
      - qty_on_hand : ปริมาณคงคลังในคลัง internal ของสาขานั้น (stock_quant.quantity)
      - qty_rented  : จำนวนที่ถูกเช่า = จำนวนที่ 'ตัดสต๊อกออกเสร็จสิ้น' ของบิลเช่า
                      ที่ยังไม่ถูกคืนครบ (ตัด - คืน) ต่อสินค้า+สาขา

    นิยาม qty_rented ใช้ตรรกะเดียวกับ so_auto_stock_cut._compute_sc_stock_flags:
      ใบตัด   = move สถานะ done, picking เป็น outgoing, ไม่ใช่ใบคืน (origin_returned_move_id IS NULL)
      จำนวนคืน = move สถานะ done ที่อ้างอิงกลับผ่าน origin_returned_move_id
      สุทธิ    = GREATEST(ตัด - คืน, 0)  (หักคืนบางส่วนได้ ไม่ติดลบ)
      สาขา     = branch ของคลังต้นทาง (fallback: branch ของ picking -> ของบิลขาย)
    """
    _name = 'dev.rental.stock.overview'
    _description = 'รายงานภาพรวมสต็อก เช่า'
    _auto = False
    _order = 'product_id, branch_id'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product', string='สินค้า', readonly=True)
    product_code = fields.Char(
        string='รหัสสินค้า', related='product_id.default_code', readonly=True)
    product_name = fields.Char(
        string='สินค้า', related='product_id.name', readonly=True)
    branch_id = fields.Many2one('res.branch', string='สาขา', readonly=True)
    uom_name = fields.Char(
        string='หน่วย', related='product_id.uom_id.name', readonly=True)
    qty_on_hand = fields.Float(
        string='ปริมาณที่มีอยู่', readonly=True, digits='Product Unit of Measure')
    qty_rented = fields.Float(
        string='จำนวนที่ถูกเช่า', readonly=True, digits='Product Unit of Measure')
    qty_lost = fields.Float(
        string='สินค้าหาย', readonly=True, digits='Product Unit of Measure')
    qty_damaged = fields.Float(
        string='สินค้าชำรุด', readonly=True, digits='Product Unit of Measure')
    qty_transferred = fields.Float(
        string='ย้ายสต็อก (เข้าสาขา/บ.อื่น)', readonly=True, digits='Product Unit of Measure')
    qty_transferred_out = fields.Float(
        string='ย้ายสต็อก (ออกสาขา/บ.อื่น)', readonly=True, digits='Product Unit of Measure')
    qty_initial = fields.Float(
        string='จำนวนตั้งต้น', readonly=True, digits='Product Unit of Measure',
        help='ปริมาณที่มีอยู่ + จำนวนที่ถูกเช่า + สินค้าหาย + สินค้าชำรุด')

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)

        # กันกรณี DB ไม่ได้ติดตั้งโมดูล customs (ไม่มีคอลัมน์ pfb_so_type)
        # -> ถ้าไม่มี ให้รวมทุกใบส่งออก done (อาจปนสินค้าขายขาด) แทนที่จะพัง
        self._cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'sale_order' AND column_name = 'pfb_so_type' LIMIT 1
        """)
        rent_filter = "AND so.pfb_so_type = 'rent'" if self._cr.fetchone() else ""

        self._cr.execute("""
            CREATE OR REPLACE VIEW {table} AS (
                WITH rental_prod AS (
                    -- สินค้าเช่า: ชื่อสินค้ามี '(R)' ต่อท้าย (ตามคอนเวนชันของ NPD)
                    SELECT pp.id AS product_id,
                           lower(trim(pt.default_code)) AS code
                      FROM product_product pp
                      JOIN product_template pt ON pt.id = pp.product_tmpl_id
                     WHERE pt.name ILIKE '%(R)%'
                ),
                onhand AS (
                    SELECT sq.product_id            AS product_id,
                           sl.branch_id             AS branch_id,
                           SUM(sq.quantity)         AS qty_on_hand
                      FROM stock_quant sq
                      JOIN stock_location sl ON sl.id = sq.location_id
                     WHERE sl.usage = 'internal'
                       AND sl.branch_id IS NOT NULL
                       AND sq.product_id IN (SELECT product_id FROM rental_prod)
                     GROUP BY sq.product_id, sl.branch_id
                ),
                cut AS (
                    SELECT sm.id           AS move_id,
                           sm.product_id   AS product_id,
                           COALESCE(src.branch_id, sp.branch_id, so.branch_id) AS branch_id,
                           sm.product_qty  AS delivered
                      FROM stock_move sm
                      JOIN stock_picking sp       ON sp.id = sm.picking_id
                      JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
                      LEFT JOIN stock_location src ON src.id = sm.location_id
                      LEFT JOIN sale_order so       ON so.id = sp.sale_id
                     WHERE sm.state = 'done'
                       AND spt.code = 'outgoing'
                       AND sm.origin_returned_move_id IS NULL
                       AND sm.product_qty > 0
                       {rent_filter}
                       AND sm.product_id IN (SELECT product_id FROM rental_prod)
                       AND COALESCE(src.branch_id, sp.branch_id, so.branch_id) IS NOT NULL
                ),
                returned AS (
                    SELECT rm.origin_returned_move_id AS move_id,
                           SUM(rm.product_qty)        AS returned_qty
                      FROM stock_move rm
                     WHERE rm.state = 'done'
                       AND rm.origin_returned_move_id IS NOT NULL
                     GROUP BY rm.origin_returned_move_id
                ),
                rented AS (
                    SELECT c.product_id AS product_id,
                           c.branch_id  AS branch_id,
                           SUM(GREATEST(c.delivered - COALESCE(r.returned_qty, 0), 0)) AS qty_rented
                      FROM cut c
                      LEFT JOIN returned r ON r.move_id = c.move_id
                     GROUP BY c.product_id, c.branch_id
                ),
                scrap AS (
                    -- สินค้าหาย / สินค้าชำรุด จากใบ Scrap (stock.scrap) เฉพาะสถานะเสร็จสิ้น
                    -- แยกประเภทจากคลังปลายทาง (scrap_location_id): 'สินค้าหาย' vs 'สินค้าชำรุด'
                    -- สาขา = คลังต้นทาง location_id.branch_id
                    -- หมายเหตุ: 'สินค้าชำรุด' เริ่มนับตั้งแต่ 7/7/2026 (เวลาไทย) เป็นต้นไปเท่านั้น
                    SELECT s.product_id AS product_id,
                           sl.branch_id AS branch_id,
                           SUM(s.scrap_qty) FILTER (WHERE dl.name ILIKE '%หาย%')   AS qty_lost,
                           SUM(s.scrap_qty) FILTER (
                               WHERE dl.name ILIKE '%ชำรุด%'
                                 AND (s.date_done AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok')::date
                                     >= DATE '2026-07-07'
                           ) AS qty_damaged
                      FROM stock_scrap s
                      JOIN stock_location sl ON sl.id = s.location_id
                      JOIN stock_location dl ON dl.id = s.scrap_location_id
                     WHERE s.state = 'done'
                       AND sl.branch_id IS NOT NULL
                       AND s.product_id IN (SELECT product_id FROM rental_prod)
                       AND (dl.name ILIKE '%หาย%' OR dl.name ILIKE '%ชำรุด%')
                     GROUP BY s.product_id, sl.branch_id
                ),
                transfer AS (
                    -- การย้ายสต็อก (stock.api.transfer) เฉพาะรายการที่สำเร็จ
                    -- นับตามคลังปลายทาง (destination_location_id.branch_id) = สาขาที่รับของเข้า
                    -- แมปรหัสสินค้า (default_code) -> สินค้าเช่า (R)
                    SELECT rp.product_id AS product_id,
                           dl.branch_id  AS branch_id,
                           SUM(tl.request_qty) AS qty_transferred
                      FROM stock_api_transfer_line tl
                      JOIN stock_location dl ON dl.id = tl.destination_location_id
                      JOIN rental_prod rp ON rp.code = lower(trim(tl.default_code))
                     WHERE tl.status = 'สำเร็จ'
                       AND dl.branch_id IS NOT NULL
                     GROUP BY rp.product_id, dl.branch_id
                ),
                transfer_out AS (
                    -- ย้ายออก: transfer ที่ต้นทางอยู่ใน db ปัจจุบัน (database_selection = ชื่อ db นี้)
                    -- ต้นทาง = คลังจริง location_id (raw id) -> stock_location.branch_id = สาขาที่ย้ายออก
                    -- ต้องกรอง database_selection = db ปัจจุบัน กัน id คลังชนกันข้าม db
                    SELECT rp.product_id AS product_id,
                           sl.branch_id  AS branch_id,
                           SUM(tl.request_qty) AS qty_transferred_out
                      FROM stock_api_transfer_line tl
                      JOIN stock_api_transfer t ON t.id = tl.transfer_id
                      JOIN stock_location sl ON sl.id = tl.location_id
                      JOIN rental_prod rp ON rp.code = lower(trim(tl.default_code))
                     WHERE tl.status = 'สำเร็จ'
                       AND t.database_selection = '{current_db}'
                       AND sl.branch_id IS NOT NULL
                     GROUP BY rp.product_id, sl.branch_id
                ),
                keys AS (
                    SELECT product_id, branch_id FROM onhand
                    UNION SELECT product_id, branch_id FROM rented
                    UNION SELECT product_id, branch_id FROM scrap
                    UNION SELECT product_id, branch_id FROM transfer
                    UNION SELECT product_id, branch_id FROM transfer_out
                )
                SELECT row_number() OVER ()                  AS id,
                       k.product_id                          AS product_id,
                       k.branch_id                           AS branch_id,
                       (COALESCE(o.qty_on_hand, 0.0)
                        + COALESCE(rt.qty_rented, 0.0)
                        + COALESCE(sc.qty_lost, 0.0)
                        + COALESCE(sc.qty_damaged, 0.0))     AS qty_initial,
                       COALESCE(o.qty_on_hand, 0.0)          AS qty_on_hand,
                       COALESCE(rt.qty_rented, 0.0)          AS qty_rented,
                       COALESCE(sc.qty_lost, 0.0)            AS qty_lost,
                       COALESCE(sc.qty_damaged, 0.0)         AS qty_damaged,
                       COALESCE(tr.qty_transferred, 0.0)     AS qty_transferred,
                       COALESCE(tro.qty_transferred_out, 0.0) AS qty_transferred_out
                  FROM keys k
                  LEFT JOIN onhand o        ON o.product_id = k.product_id AND o.branch_id = k.branch_id
                  LEFT JOIN rented rt       ON rt.product_id = k.product_id AND rt.branch_id = k.branch_id
                  LEFT JOIN scrap sc        ON sc.product_id = k.product_id AND sc.branch_id = k.branch_id
                  LEFT JOIN transfer tr     ON tr.product_id = k.product_id AND tr.branch_id = k.branch_id
                  LEFT JOIN transfer_out tro ON tro.product_id = k.product_id AND tro.branch_id = k.branch_id
            )
        """.format(table=self._table, rent_filter=rent_filter,
                   current_db=self.env.cr.dbname))
