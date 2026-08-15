from odoo import api, fields, models
from odoo.exceptions import UserError
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    start_x_date = fields.Date(string='วันที่เริ่มต้นการเช่า', compute='_compute_rent_dates', store=True)
    end_x_date = fields.Date(string='วันที่สิ้นสุดการเช่า', compute='_compute_rent_dates', store=True)
    branch_id = fields.Many2one('res.branch', string='Branch')

    deposit_return_state = fields.Selection(
        selection=[
            ('not_returned', 'ยังไม่คืนเงิน'),
            ('returned', 'คืนเงินแล้ว')
        ],
        string='สถานะการคืนเงินประกัน',
        default='not_returned',  # ค่าเริ่มต้นเปลี่ยนเป็น 'ยังไม่คืนเงิน'
        store=True
    )

    no_deduction = fields.Boolean(string="ไม่หักค่าประกัน", default=False)

    @api.depends('branch_id')
    def _compute_rent_dates(self):
        db_name = self.env.cr.dbname
        if db_name == "NPD_Bangkok_New" or db_name == "NPD_S_Group_New" or db_name =="test" or db_name =="NPD_S_Group_New_V2" or db_name =="test_2025_02" or db_name =="NPD_Intertrading_New" or db_name =="NPD_Intertrading_New_NonVat":
            print("db_name",db_name)
            for picking in self:
                print(f"Computing rent dates for Picking ID: {picking.id}")
                if picking.branch_id:
                    # หา sale.order ที่เกี่ยวข้องกับ stock.picking นี้

                    # sale_order = self.env['sale.order'].search([
                    #     ('branch_id', '=', picking.branch_id.id),
                    #     ('name', '=', picking.origin)
                    # ], limit=1)
                    sale_order = self.env['sale.order'].search([
                        # ('branch_id', '=', picking.branch_id.id),
                        ('name', '=', picking.origin)
                    ], limit=1)
                    if sale_order:
                        # print(f"Found Sale Order ID: {sale_order.id} for Picking name: {picking.origin}")
                        picking.start_x_date = sale_order.start_rent_date
                        picking.end_x_date = sale_order.end_rent_date


    @api.model
    def create(self, vals):
        picking = super(StockPicking, self).create(vals)
        print(f"Created Picking ID: {picking.id} with vals: {vals}")
        return picking

    def write(self, vals):

        res = super(StockPicking, self).write(vals)
        print(f"Writing to Picking ID(s): {self.ids} with vals: {vals}")
        if 'branch_id' in vals:
            self._compute_rent_dates()
        return res

    def update_location_from_branch(self):

        for picking in self:
            origin_prefix = picking.origin[:2]
            print("origin_prefix", origin_prefix)

            if picking.group_id and picking.group_id.name:
                group_name = picking.group_id.name[:2]
            else:
                group_name = ''
            # print("group_id", group_name)

            if group_name == 'SO':
                if picking.branch_id:
                    # ค้นหา stock.location ที่สัมพันธ์กับ branch_id ของ picking
                    default_location = self.env['stock.location'].search([
                        ('branch_id', '=', picking.branch_id.id),
                        ('usage', '=', 'internal')  # เงื่อนไข: ใช้ location แบบ internal
                    ], limit=1)

                    sale_order = self.env['sale.order'].search([
                        ('name', '=', picking.origin)
                    ], limit=1)

                    if default_location:
                        picking.force_date = fields.Datetime.now()
                        picking.start_x_date = sale_order.start_rent_date
                        picking.end_x_date = sale_order.end_rent_date

                        for move_line in picking.move_line_ids:
                            if move_line.location_dest_id != default_location:
                                if "IN" in picking.name.upper():
                                    # print(
                                    #     f"Updating location_id for Move Line ID: {move_line.id} to Location ID: {default_location.id}")

                                    move_line.location_dest_id = default_location.id



            if origin_prefix == 'SR':
                stock_request = self.env['stock.request'].search([
                    ('name', '=', picking.origin)
                ], limit=1)
                print("**stock_request",stock_request.location_id)
                default_location = self.env['stock.location'].search([
                    ('id', '=', stock_request.location_src_id.id)
                ], limit=1)

                # print("**default_location", default_location.name)

                if default_location:
                    picking.write({
                        'force_date': fields.Datetime.now(),
                        'branch_id': self.env.user.branch_id.id,
                    })
                    if picking.location_dest_id:
                        default_location = picking.location_dest_id

                        move_lines = self.env['stock.move'].search([
                            ('picking_id', '=', picking.id)
                        ])

                        for move in move_lines:
                            # print(f"🔍 ตรวจสอบ Line: {move.product_id.display_name} (Move ID: {move.id})")

                            # ตรวจสอบว่าไม่มี move_line
                            if not move.move_line_ids:
                                # print(f"➕ ยังไม่มี move_line สร้างใหม่ให้สินค้า: {move.product_id.display_name}")

                                self.env['stock.move.line'].create({
                                    'move_id': move.id,
                                    'picking_id': picking.id,
                                    'product_id': move.product_id.id,
                                    'product_uom_id': move.product_uom.id,
                                    'qty_done': move.product_uom_qty,  # ปริมาณที่ต้องเคลื่อนย้าย
                                    'location_id': default_location.id,
                                    'location_dest_id': picking.location_dest_id.id,
                                })
                            # else:
                            #     print(f"✅ มี move_line แล้วสำหรับสินค้า: {move.product_id.display_name}")

                        for move_line in picking.move_line_ids:
                            # ตรวจสอบว่าต้องอัพเดท location_id หรือไม่
                            # print("record.name********************", move_line.product_id.name)

                            # ✅ เช็คว่า record.name มีคำว่า "อิน"
                            if "IN" in picking.name.upper():  # แปลงเป็นตัวใหญ่ก่อนเช็ค
                                # print(f"✅ product_id : {move_line.product_id.id}")
                                # print(f"✅ product_name : {move_line.product_id.name}")
                                # print(f"✅ location_dest_id: {picking.location_dest_id.name}")
                                move_line.location_dest_id = picking.location_dest_id.id

        return True

    def action_assign(self):
        res = super(StockPicking, self).action_assign()
        # print(f"Action Assign called for Picking ID(s): {self.ids}")
        self.update_location_from_branch()

        # 🔔 ตรวจสอบจากยอดคงเหลือจริง (on-hand) ของสาขา แทนการเช็คการจอง (reservation)
        #    - ไม่สนใจว่าใบอื่นจองไว้หรือไม่ (ตัดปัญหาการจองชนกันชั่วคราว + rollback ทั้งใบ)
        #    - บล็อกเฉพาะกรณีสินค้าไม่มีของอยู่จริงในสาขา
        #    - สต็อกจะถูกตัดตอนส่งมอบ (validate OUT) และคืนตอนรับคืน (validate IN) ตามปกติ
        if self.env.cr.dbname != 'NPD_Logistics_New':
            for picking in self:
                # บิลย้อนหลัง/ย้ายระบบ: ข้ามด่านเช็ก on-hand ทั้งใบ
                #   ปล่อยให้จอง/ยืนยัน + สร้างใบตัด (OUT) / ใบคืน (IN) ได้ตามปกติ
                #   แม้ยอดคงเหลือปัจจุบันของสาขาจะไม่พอ (เพราะเป็นบิลเก่าที่ไม่ควรอิงสต๊อกวันนี้)
                #   หา SO แบบทนทาน: จาก move.sale_line_id ก่อน (ผูกตรง) ค่อย fallback ที่ origin
                orders = picking.move_lines.sudo().mapped('sale_line_id.order_id')
                if not orders and picking.origin:
                    orders = self.env['sale.order'].sudo().search(
                        [('name', '=', picking.origin)], limit=1)
                if orders and any(
                    hasattr(o, '_is_stock_skip_migrated') and o._is_stock_skip_migrated()
                    for o in orders
                ):
                    continue

                out_of_stock = []
                branch_name = picking.branch_id.name or 'ไม่ทราบสาขา'
                for move in picking.move_lines:
                    # ข้าม move ที่จบแล้ว/ยกเลิก และข้ามใบรับคืน (ต้นทางไม่ใช่ location ภายใน)
                    if move.state in ('done', 'cancel'):
                        continue
                    if move.location_id.usage != 'internal':
                        continue
                    # ย้ายภายในสาขาเดียวกัน (ต้นทาง=ปลายทาง) เป็น net-zero ไม่ต้องเช็ก on-hand
                    #   ใช้กับบิลย้อนหลังที่ตัด/คืนแบบ loopback (ไม่กระทบ quant)
                    if move.location_id.id == move.location_dest_id.id:
                        continue

                    # จำนวนที่ต้องใช้จริง (หน่วยอ้างอิงของสินค้า)
                    #   ใบเช่า: product_uom_qty = จำนวนสินค้า x จำนวนวันที่เช่า (ใช้คิดค่าเช่า)
                    #   จำนวนของที่ต้องหยิบออกจากคลังจริง ๆ คือ pfb_quantity เท่านั้น
                    need_qty = move.product_qty
                    line = move.sale_line_id if 'sale_line_id' in move._fields else False
                    if line and 'pfb_quantity' in line._fields and 'pfb_so_type' in line.order_id._fields:
                        if line.order_id.pfb_so_type == 'rent' and line.pfb_quantity:
                            need_qty = line.product_uom._compute_quantity(
                                line.pfb_quantity, move.product_id.uom_id
                            )

                    # หา location ของสาขาที่อยู่ "ภายใต้" location ต้นทางของ move
                    #   - เจอ  -> นับเฉพาะสต็อกสาขานั้น (ไม่รวมสาขาอื่นที่อยู่ใต้ location แม่เดียวกัน)
                    #   - ไม่เจอ -> ใช้ location เดิมตามพฤติกรรมก่อนหน้า
                    #   ⚠ หนึ่งสาขาอาจมีหลาย location (เช่น ปลวกแดง มี 2 คลัง) ต้องนับรวมทุกตัว
                    #     ห้ามใช้ limit=1 เพราะจะไปเจอคลังที่ไม่มีของแล้วฟ้องว่าสต็อก 0
                    src_locations = move.location_id
                    if picking.branch_id:
                        branch_locations = self.env['stock.location'].sudo().search([
                            ('branch_id', '=', picking.branch_id.id),
                            ('usage', '=', 'internal'),
                            ('id', 'child_of', move.location_id.id),
                        ])
                        if branch_locations:
                            src_locations = branch_locations

                    # ยอดคงเหลือจริงของทุก location ในสาขา (รวม sub-location) ในหน่วยอ้างอิงของสินค้า
                    #   อ่านจาก stock.quant ตรง ๆ ด้วย sudo() กัน ir.rule ราย branch
                    #   ทำให้ผู้ใช้ต่างสาขามองไม่เห็นสต็อกแล้วนับได้ 0
                    quants = self.env['stock.quant'].sudo().search([
                        ('product_id', '=', move.product_id.id),
                        ('location_id', 'child_of', src_locations.ids),
                    ])
                    onhand = sum(quants.mapped('quantity'))
                    if onhand < need_qty:
                        checked = ', '.join(src_locations.sudo().mapped('complete_name'))
                        out_of_stock.append(
                            f"- {move.product_id.display_name}: ต้องการ {need_qty} {move.product_id.uom_id.name} "
                            f"แต่คงเหลือจริง {onhand} ❌ สาขา: {branch_name} (ตรวจที่: {checked})"
                        )

                if out_of_stock:
                    msg = "\n".join(out_of_stock)
                    raise UserError(f"❌ สินค้าคงเหลือในสาขาไม่พอ:\n\n{msg}")

        return res

    # def auto_fill_branch_id(self):
    #     for picking in self:
    #         if picking.branch_id:
    #             # ค้นหา stock.location ที่สัมพันธ์กับ branch_id ของ picking
    #             default_location = self.env['stock.location'].search([
    #                 ('branch_id', '=', picking.branch_id.id),
    #                 ('usage', '=', 'internal')  # เงื่อนไข: ใช้ location แบบ internal
    #             ], limit=1)
    #             if default_location:
    #                 for move_line in picking.move_line_ids:
    #                     # ตรวจสอบว่าต้องอัพเดท location_id หรือไม่
    #                     if move_line.location_id != default_location:
    #                         print(
    #                             f"Updating location_id for Move Line ID: {move_line.id} to Location ID: {default_location.id}")
    #                         move_line.location_dest_id = default_location.id
    #             else:
    #                 print(f"No default location found for Branch ID: {picking.branch_id.id}")
    #         else:
    #             print(f"No Branch ID found for Picking ID: {picking.id}")
    #
    #     return True
    #
    # def action_pack_operation_auto_fill(self):
    #     res1 = super(StockPicking, self).action_pack_operation_auto_fill()
    #     print(f"Action Assign called for Picking ID(s): {self.ids}")
    #     self.auto_fill_branch_id()
    #
    #     return res1