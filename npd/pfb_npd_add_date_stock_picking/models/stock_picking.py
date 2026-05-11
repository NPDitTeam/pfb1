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

        # 🔔 ตรวจสอบสินค้าที่จองไม่ได้
        if self.env.cr.dbname != 'NPD_Logistics_New':
            for picking in self:
                out_of_stock = []
                branch_name = picking.branch_id.name or 'ไม่ทราบสาขา'
                for move in picking.move_lines:
                    if move.state == 'confirmed' and move.reserved_availability <= 0:
                        out_of_stock.append(
                            f"- {move.product_id.display_name} ({move.product_uom_qty} {move.product_uom.name}) ❌ สาขา: {branch_name}"
                        )

                if out_of_stock:
                    msg = "\n".join(out_of_stock)
                    raise UserError(f"❌ พบสินค้าที่ไม่มีสต็อกในสาขา ไม่สามารถจองได้:\n\n{msg}")

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