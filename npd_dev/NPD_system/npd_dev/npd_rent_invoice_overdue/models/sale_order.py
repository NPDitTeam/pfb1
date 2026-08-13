# -*- coding: utf-8 -*-
"""ข้อมูลหนี้ค้างชำระสำหรับรายงาน 'ใบกำกับการเช่าหนี้ค้างชำระ'

หลักการ (ตรวจสอบด้วย SQL บน NPD_Intertrading_New แล้ว):

  หา SO อื่นของลูกค้ารายเดียวกัน ที่ **มีใบแจ้งหนี้ค้างชำระ** -- นับ 3 ทาง
    - ใบแจ้งหนี้ปกติ      : ผูกผ่าน sale_order_line_invoice_rel (INV-xxx)
    - ใบแจ้งหนี้ค่าประกัน : ผูกผ่าน rent_check / account_move_sale_order_rel (INS-xxx)
    - ใบเพิ่มหนี้ (Add Debit Note จากหน้าใบแจ้งหนี้) : debit_origin_id -> ใบแจ้งหนี้
      ต้นทาง -> SO  (สำรองด้วย invoice_origin) ประเภทดูจาก reason_code_id
      = สินค้าหาย / ค่าเช่าส่วนต่าง / สินค้าชำรุด
      ใบเพิ่มหนี้ขึ้นเฉพาะ 'ยอดเงิน' ในตารางสรุป ไม่ดึงรายการสินค้ามาแสดง
  โดยนับเฉพาะ state='posted' และ payment_state in ('not_paid','partial')

  สถานะการคืนสินค้า **ไม่ได้ใช้กรองหนี้** แต่ใช้ตัดสินว่าจะดึงสินค้ามาแสดงไหม
  (ยืนยันกับผู้ใช้แล้ว 11 ส.ค. 2026):
    - ค้างชำระ + ยังไม่กดคืน  -> ขึ้นตารางสรุป **และ** ดึงรายการสินค้ามาแสดง
    - ค้างชำระ + คืนของครบแล้ว -> ขึ้นแค่ยอดในตารางสรุป ไม่ดึงสินค้า
  นิยาม 'ยังไม่กดคืน' ใช้ตรรกะเดียวกับ npd_rental_return_tracking:
    ใบตัด   = stock.move state=done, picking ขาออก, origin_returned_move_id IS NULL
    จำนวนคืน = stock.move state=done ที่อ้างกลับผ่าน origin_returned_move_id

  และ **ไม่นับ SO ใบที่กำลังพิมพ์อยู่** (ตามที่ผู้ใช้ระบุ: ค้างชำระจะไม่มองใบล่าสุดที่ print)

  รายการสินค้าของ SO เหล่านั้นถูกดึงมาแสดงต่อท้ายตารางสินค้า พร้อมคอลัมน์
  'อ้างอิงเลขเอกสาร' (แสดงเฉพาะเลขเอกสาร ไม่แสดงช่วงวันที่)
  และ **ไม่ถูกนำไปคิดยอดรวม** ของใบกำกับนี้

  ดึงสินค้ามากี่รายการ ขึ้นกับวันที่เช่าว่าตรงกับใบที่กำลังพิมพ์ไหม
    - วันเริ่ม/วันสิ้นสุด **ตรงกัน**    = เช่ารอบเดียวกัน -> เอาเฉพาะสินค้าที่มี
      เหมือนกันกับใบที่กำลังพิมพ์ (ตัวที่ใบนี้ไม่มี ไม่ต้องเอามา)
    - วันเริ่ม/วันสิ้นสุด **ไม่ตรงกัน** = คนละรอบเช่า -> เอาสินค้าทั้งหมดของใบนั้น
"""
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

# ยอดค้างชำระขั้นต่ำที่จะนำมาแสดง
# ตั้ง 0.01 = แสดงทุกบาททุกสตางค์ (ตามที่ผู้ใช้ระบุ 13 ส.ค. 2026)
# ถ้าไม่อยากให้ใบกำกับรกด้วยเศษสตางค์จากการปัดเศษตอนรับชำระบางส่วน
# (ใน DB จริงพบเหลือ 0.15 / 0.50 / 0.68 บาท) ให้ปรับกลับเป็น 1.0
RESIDUAL_MIN = 0.01


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ------------------------------------------------------------------
    # แท็บ 'สรุปยอดค้างชำระ' บนฟอร์มใบสั่งเช่า
    # ------------------------------------------------------------------
    overdue_line_ids = fields.One2many(
        'npd.rent.overdue.line', 'order_id',
        string=u'สรุปยอดค้างชำระ',
        compute='_compute_overdue_lines', readonly=True,
        help=u'ใบแจ้งหนี้/ใบแจ้งหนี้ค่าประกันของลูกค้ารายนี้ที่ยังค้างชำระ '
             u'(ไม่นับใบสั่งเช่าใบนี้) ตัวเลขชุดเดียวกับที่พิมพ์ในใบกำกับ')
    overdue_total = fields.Monetary(
        string=u'รวมยอดค้างชำระ', compute='_compute_overdue_lines',
        currency_field='currency_id')
    overdue_count = fields.Integer(
        string=u'จำนวนใบที่ค้างชำระ', compute='_compute_overdue_lines')

    def _compute_overdue_lines(self):
        """สร้างบรรทัดสรุปสด ๆ ทุกครั้งที่เปิดฟอร์ม

        ฟิลด์นี้ไม่ได้ store จึงถูกคำนวณเฉพาะตอนที่ view ขอ (คือตอนเปิดฟอร์ม)
        list view ของใบสั่งเช่าจะไม่โดนคำนวณ
        """
        Line = self.env['npd.rent.overdue.line']
        for order in self:
            lines = Line.browse()
            total = 0.0
            if order.id and order.partner_id:
                vals = []
                for item in order.get_overdue_rent_data()['summary']:
                    total += item['amount']
                    vals.append({
                        'order_id': order.id,
                        'sale_id': item['so_id'],
                        'move_id': item['move_id'],
                        'invoice_name': item['invoice_name'],
                        'invoice_date': item['invoice_date_raw'],
                        'pay_type': ('partial' if item['payment_state'] == 'partial'
                                     else 'not_paid'),
                        'doc_type': item['doc_type'],
                        'amount_residual': item['amount'],
                        'currency_id': order.currency_id.id,
                        'return_state': ('not_returned'
                                         if item['qty_outstanding'] > 0
                                         else 'returned'),
                    })
                if vals:
                    lines = Line.create(vals)
            order.overdue_line_ids = lines
            order.overdue_total = total
            order.overdue_count = len(lines)

    def action_confirm(self):
        """ยืนยันใบสั่งขาย -> คำนวณยอดค้างชำระใหม่ทันที

        ฟิลด์นี้ไม่ได้ store จึงคำนวณสดอยู่แล้วทุกครั้งที่เปิดฟอร์ม
        แต่ตอนกดยืนยัน ค่าที่ค้างอยู่ใน cache ของรอบนั้นอาจเป็นของก่อนยืนยัน
        จึงล้าง cache แล้วคำนวณใหม่ ให้ตัวเลขบนแท็บตรงกับสถานะหลังยืนยันแน่นอน
        """
        res = super(SaleOrder, self).action_confirm()
        fnames = ['overdue_line_ids', 'overdue_total', 'overdue_count']
        try:
            self.invalidate_cache(fnames=fnames, ids=self.ids)
            self._compute_overdue_lines()
        except Exception:
            # การยืนยันใบสั่งขายต้องไม่ล้มเพราะส่วนสรุปหนี้
            _logger.exception(
                u'คำนวณยอดค้างชำระตอนยืนยัน %s ไม่สำเร็จ', self.mapped('name'))
        return res

    # ------------------------------------------------------------------
    # helper
    # ------------------------------------------------------------------
    @staticmethod
    def _overdue_format_date(value):
        """date -> 'dd/mm/พ.ศ.' เช่น 16/07/2569 (ใบนี้ใช้ปี พ.ศ. ทั้งใบ)"""
        if not value:
            return ''
        return '%02d/%02d/%d' % (value.day, value.month, value.year + 543)

    def _overdue_has_column(self, table, column):
        """เช็คว่ามีคอลัมน์นี้จริงหรือไม่ (กัน DB ที่ไม่ได้ติดตั้งโมดูล customs)"""
        self._cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = %s AND column_name = %s LIMIT 1
        """, (table, column))
        return bool(self._cr.fetchone())

    def _overdue_has_table(self, table):
        self._cr.execute("""
            SELECT 1 FROM information_schema.tables WHERE table_name = %s LIMIT 1
        """, (table,))
        return bool(self._cr.fetchone())

    def _overdue_related_so_sql(self):
        """SQL หา SO อื่นของลูกค้าเดียวกันที่มีใบแจ้งหนี้ค้างชำระ

        คืนค่า (sql, params) -- แต่ละแถว = 1 ใบแจ้งหนี้ที่ค้างชำระ
        """
        self.ensure_one()

        # ใบแจ้งหนี้ค่าประกัน (rent_check) มีเฉพาะเมื่อติดตั้งโมดูล customs
        if self._overdue_has_table('account_move_sale_order_rel'):
            deposit_union = """
                UNION
                SELECT r.sale_order_id, r.account_move_id, 'deposit'
                  FROM account_move_sale_order_rel r
                  JOIN account_move am ON am.id = r.account_move_id
                 WHERE am.move_type = 'out_invoice'
                   AND am.debit_origin_id IS NULL
            """
        else:
            deposit_union = ""

        # ประเภทสินค้าของใบเพิ่มหนี้ (สินค้าหาย / ค่าเช่าส่วนต่าง / สินค้าชำรุด)
        if (self._overdue_has_column('account_move', 'reason_code_id')
                and self._overdue_has_table('scrap_reason_code')):
            reason_join = "LEFT JOIN scrap_reason_code rc ON rc.id = am.reason_code_id"
            reason_col = "rc.name"
        else:
            reason_join = ""
            reason_col = "NULL::varchar"

        # กัน DB ที่ไม่มีคอลัมน์ pfb_so_type -> ไม่กรองประเภทเช่า
        rent_filter = ("AND so.pfb_so_type = 'rent'"
                       if self._overdue_has_column('sale_order', 'pfb_so_type') else "")

        sql = """
            WITH inv_link AS (
                -- ใบแจ้งหนี้ปกติ: ผูกผ่านบรรทัดของใบสั่งขาย
                -- (ตัดใบเพิ่มหนี้ออก เพราะไปรวมใน debit_link แทน จะได้ไม่นับซ้ำ)
                SELECT DISTINCT sol.order_id AS so_id, am.id AS move_id,
                       'invoice'::text AS kind
                  FROM sale_order_line sol
                  JOIN sale_order_line_invoice_rel rel ON rel.order_line_id = sol.id
                  JOIN account_move_line aml ON aml.id = rel.invoice_line_id
                  JOIN account_move am ON am.id = aml.move_id
                 WHERE am.move_type = 'out_invoice'
                   AND am.debit_origin_id IS NULL
                {deposit_union}
            ),
            debit_link AS (
                -- ใบเพิ่มหนี้ (กด Add Debit Note จากหน้าใบแจ้งหนี้)
                -- เช่น สินค้าหาย / ค่าเช่าส่วนต่าง / สินค้าชำรุด
                -- โยงกลับหา SO ผ่านใบแจ้งหนี้ต้นทาง ถ้าไม่ได้ค่อยใช้ invoice_origin
                -- (ตรวจกับข้อมูลจริง 259 ใบ ทั้งสองทางให้ SO เดียวกันหมด)
                SELECT DISTINCT COALESCE(il.so_id, org.id) AS so_id,
                       dn.id AS move_id, 'debit'::text AS kind
                  FROM account_move dn
             LEFT JOIN inv_link il ON il.move_id = dn.debit_origin_id
             LEFT JOIN sale_order org ON org.name = dn.invoice_origin
                 WHERE dn.move_type = 'out_invoice'
                   AND dn.debit_origin_id IS NOT NULL
                   AND COALESCE(il.so_id, org.id) IS NOT NULL
            ),
            all_link AS (
                SELECT * FROM inv_link
                UNION
                SELECT * FROM debit_link
            ),
            returned AS (
                -- จำนวนที่คืนกลับแล้ว รวมเข้าที่ move ตัดต้นทาง
                SELECT rm.origin_returned_move_id AS move_id,
                       SUM(rm.product_qty) AS returned_qty
                  FROM stock_move rm
                 WHERE rm.state = 'done'
                   AND rm.origin_returned_move_id IS NOT NULL
                 GROUP BY rm.origin_returned_move_id
            ),
            not_returned AS (
                -- จำนวนที่ยังไม่ได้กดคืน ต่อ 1 SO (ไม่ได้ใช้กรองใบแจ้งหนี้
                -- ใช้แค่ตัดสินว่าจะดึงรายการสินค้าของ SO นั้นมาแสดงหรือไม่)
                SELECT sp.sale_id AS so_id,
                       SUM(GREATEST(sm.product_qty - COALESCE(r.returned_qty, 0.0), 0.0))
                           AS qty_outstanding
                  FROM stock_move sm
                  JOIN stock_picking sp ON sp.id = sm.picking_id
                  JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
             LEFT JOIN returned r ON r.move_id = sm.id
                 WHERE sm.state = 'done'
                   AND spt.code = 'outgoing'
                   AND sm.origin_returned_move_id IS NULL
                   AND sp.sale_id IS NOT NULL
                 GROUP BY sp.sale_id
            )
            SELECT so.id                AS so_id,
                   so.name              AS so_name,
                   so.start_rent_date   AS start_rent_date,
                   so.end_rent_date     AS end_rent_date,
                   am.id                AS move_id,
                   am.name              AS invoice_name,
                   am.invoice_date      AS invoice_date,
                   am.payment_state     AS payment_state,
                   il.kind              AS kind,
                   {reason_col}         AS reason_name,
                   am.amount_residual   AS amount_residual,
                   COALESCE(nr.qty_outstanding, 0.0) AS qty_outstanding
              FROM all_link il
              JOIN sale_order so ON so.id = il.so_id
              JOIN account_move am ON am.id = il.move_id
              {reason_join}
         LEFT JOIN not_returned nr ON nr.so_id = so.id
             WHERE so.partner_id = %s
               AND so.id <> %s
               AND so.state IN ('sale', 'done')
               {rent_filter}
               AND am.state = 'posted'
               AND am.payment_state IN ('not_paid', 'partial')
               AND am.amount_residual >= %s
             ORDER BY so.name, il.kind DESC, am.invoice_date, am.name
        """.format(deposit_union=deposit_union, rent_filter=rent_filter,
                   reason_join=reason_join, reason_col=reason_col)

        return sql, (self.partner_id.id, self.id, RESIDUAL_MIN)

    # ------------------------------------------------------------------
    # API สำหรับรายงาน
    # ------------------------------------------------------------------
    def get_overdue_rent_data(self):
        """คืนข้อมูลหนี้ค้างชำระของลูกค้ารายนี้ (ไม่รวมใบที่กำลังพิมพ์)

        return {
            'lines'  : [{'ref_doc','date_match','line'(sale.order.line)}, ...],
            'summary': [{'so_name','invoice_name','invoice_date','doc_type','amount'}, ...],
            'total'  : float,   # ยอดค้างชำระรวม
        }
        """
        self.ensure_one()
        empty = {'lines': [], 'summary': [], 'total': 0.0}

        if not self.partner_id:
            return empty

        try:
            sql, params = self._overdue_related_so_sql()
            self._cr.execute(sql, params)
            rows = self._cr.dictfetchall()
        except Exception:
            # รายงานต้องพิมพ์ออกได้เสมอ -- ถ้า query พังให้ข้ามส่วนนี้ไป
            _logger.exception(
                u'ใบกำกับการเช่าหนี้ค้างชำระ: หาข้อมูลหนี้ค้างของ %s ไม่สำเร็จ', self.name)
            return empty

        if not rows:
            return empty

        summary = []
        total = 0.0
        so_seen = {}   # so_id ที่มีสิทธิ์ถูกดึงรายการสินค้ามาแสดง
        seen_moves = set()

        for row in rows:
            # กันนับซ้ำ ถ้าใบแจ้งหนี้ใบเดียวถูกโยงมาได้หลายทาง
            if row['move_id'] in seen_moves:
                continue
            seen_moves.add(row['move_id'])

            amount = row['amount_residual'] or 0.0
            is_debit = row['kind'] == 'debit'
            if is_debit:
                # ใบเพิ่มหนี้ -> ใช้ชื่อ 'ประเภทสินค้า' ที่ระบุไว้บนใบเป็นตัวบอกประเภท
                # (สินค้าหาย / ค่าเช่าส่วนต่าง / สินค้าชำรุด)
                doc_type = row['reason_name'] or u'ใบเพิ่มหนี้'
            elif row['kind'] == 'deposit':
                doc_type = u'ใบแจ้งหนี้ค่าประกัน'
            else:
                doc_type = u'ใบแจ้งหนี้'

            summary.append({
                'so_id': row['so_id'],
                'move_id': row['move_id'],
                'so_name': row['so_name'] or '',
                'invoice_name': row['invoice_name'] or '',
                'invoice_date_raw': row['invoice_date'],
                'invoice_date': self._overdue_format_date(row['invoice_date']),
                'payment_state': row['payment_state'],
                'pay_type': (u'ค้างชำระบางส่วน' if row['payment_state'] == 'partial'
                             else u'ค้างชำระเต็มจำนวน'),
                'qty_outstanding': row['qty_outstanding'] or 0.0,
                'is_debit': is_debit,
                'doc_type': doc_type,
                'amount': amount,
            })
            total += amount

            # ใบเพิ่มหนี้ให้ขึ้นแค่ยอดเงิน ไม่ใช่เหตุให้ดึงสินค้าของ SO นั้นมาแสดง
            if is_debit:
                continue
            if row['so_id'] not in so_seen:
                so_seen[row['so_id']] = {
                    'name': row['so_name'] or '',
                    # ตรงรอบเช่ากับใบที่กำลังพิมพ์ไหม (เก็บไว้เผื่อใช้ ไม่ได้แสดงบนใบ)
                    'date_match': (row['start_rent_date'] == self.start_rent_date
                                   and row['end_rent_date'] == self.end_rent_date),
                    # ยังมีของค้างคืนอยู่หรือไม่ (0 = กดคืนครบแล้ว)
                    'qty_outstanding': row['qty_outstanding'] or 0.0,
                }

        # ดึงรายการสินค้า -- เฉพาะ SO ที่ "ยังไม่กดคืน" เท่านั้น
        # ถ้าคืนของครบแล้วแต่ยังค้างเงิน ให้ขึ้นแค่ยอดในตารางสรุป ไม่ต้องดึงสินค้า
        # (ของคืนไปแล้ว ไม่มีเหตุต้องเอามาแสดงในใบกำกับการเช่า)
        #
        # วันที่เช่าตรงกัน = เป็นการเช่ารอบเดียวกัน -> เอาเฉพาะ 'สินค้าที่มีเหมือนกัน'
        #                    กับใบที่กำลังพิมพ์ (ตัวที่ใบนี้ไม่มี ไม่ต้องเอามา)
        # วันที่เช่าไม่ตรงกัน = คนละรอบเช่า -> เอาสินค้าทั้งหมดของใบนั้นมาแสดง
        own_products = set(
            l.product_id.id for l in self.order_line
            if not l.display_type and l.product_id)

        lines = []
        order_ids = sorted(so_seen, key=lambda i: so_seen[i]['name'])
        for so_id in order_ids:
            info = so_seen[so_id]
            if info['qty_outstanding'] <= 0:
                continue
            order = self.env['sale.order'].browse(so_id)
            for line in order.order_line:
                if line.display_type:  # section / note
                    continue
                if info['date_match'] and line.product_id.id not in own_products:
                    continue
                lines.append({
                    'ref_doc': info['name'],
                    'date_match': info['date_match'],
                    'line': line,
                })

        return {'lines': lines, 'summary': summary, 'total': total}

    # ------------------------------------------------------------------
    # ข้อมูลสำเร็จรูปสำหรับ template (เรียกครั้งเดียวต่อ 1 เอกสาร)
    # ------------------------------------------------------------------
    def _overdue_row_from_line(self, line, ref_doc='', is_own=True):
        """แปลง sale.order.line -> dict สำหรับวาดตาราง (คอลัมน์เหมือนใบกำกับเดิม)"""
        qty = line.pfb_quantity or 0.0
        return {
            'is_own': is_own,
            'ref_doc': ref_doc,
            'name': line.product_template_id.name or '',
            'weight': (line.second_uom_qty or 0.0) * qty,
            'qty': qty,
            'insurance': line.pfb_insurance_price or 0.0,
            'price_unit': line.price_unit_no_vat or 0.0,
            'subtotal': line.price_subtotal or 0.0,
        }

    def get_overdue_rent_report_data(self):
        """ข้อมูลทั้งหมดที่ template ต้องใช้ -- เรียกครั้งเดียวแล้ว t-set เก็บไว้

        return {
            'rows'    : [dict, ...]   รายการของตัวเอง + รายการที่ดึงมา (ต่อท้าย)
            'summary' : [dict, ...]   ตารางสรุปยอดค้างชำระ
            'total'   : float         ยอดค้างชำระรวม
        }

        หมายเหตุ: rows ที่ is_own = False คือรายการที่ดึงมาจากเอกสารอื่น
        **ไม่ถูกนำไปคิดยอดรวมของใบกำกับนี้** (ยอดรวมยังใช้ doc.amount_* ตามเดิม)

        การแบ่งหน้า: ไม่ได้ทำเอง ปล่อยให้ wkhtmltopdf ตัดหน้าตามเนื้อหาจริง
        (วัดแล้ว 1 หน้าใส่ได้ ~26 บรรทัด และมันขึ้นหัวตารางให้ใหม่ทุกหน้าเอง
         เพราะหัวตารางอยู่ใน thead) -- ถ้าไปบังคับตัดหน้าเองจะเหลือที่ว่างทิ้ง
        """
        self.ensure_one()

        rows = [self._overdue_row_from_line(l)
                for l in self.order_line if not l.display_type]

        data = self.get_overdue_rent_data()
        for item in data['lines']:
            rows.append(self._overdue_row_from_line(
                item['line'], ref_doc=item['ref_doc'], is_own=False))

        return {
            'rows': rows,
            'summary': data['summary'],
            'total': data['total'],
            'has_overdue': bool(data['summary']),
            # ไม่มีรายการที่ดึงมาเลย -> ซ่อนคอลัมน์อ้างอิงเลขเอกสาร
            # เอาที่ว่างไปให้ชื่อสินค้าแทน
            'has_ref': any(not r['is_own'] for r in rows),
        }
