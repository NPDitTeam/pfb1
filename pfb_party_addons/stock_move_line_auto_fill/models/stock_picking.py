# Copyright 2017 ACSONE SA/NV
# Copyright 2018 JARSA Sistemas S.A. de C.V.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    action_pack_op_auto_fill_allowed = fields.Boolean(
        compute="_compute_action_pack_operation_auto_fill_allowed"
    )
    auto_fill_operation = fields.Boolean(
        string="Auto fill operations",
        related="picking_type_id.auto_fill_operation",
    )
    branch_id = fields.Many2one(
        'res.branch',  # ชื่อโมเดลที่อ้างอิง
        string='Branch',
        ondelete='set null'
    )

    force_date = fields.Datetime(
        string="Force Date",
        default=fields.Datetime.now,  # ดึงวันที่และเวลาปัจจุบันมาแสดง
        required=True
    )

    force_date_readonly = fields.Boolean(
        string="Force Date Readonly",
        store=True
    )

    @api.depends("state", "move_line_ids")
    def _compute_action_pack_operation_auto_fill_allowed(self):
        # print("xxxxxxxxxxxxxxxxxxxxxxx")

        for record in self:
            record.force_date_readonly = self.env.user.force_date_readonly

            # ตรวจสอบว่า force_date เป็นค่าว่าง
            if not record.force_date:
                # ใช้ fields.Datetime.now() เพื่อดึงวันที่ปัจจุบัน
                record.force_date = fields.Datetime.now()

            if record.group_id and record.group_id.name:
                group_name = record.group_id.name[:2]
            else:
                group_name = ''

            # print("group_id", group_name)

            if record.branch_id and  group_name == 'SO':

                    # ค้นหา stock.location ที่สัมพันธ์กับ branch_id ของ picking
                    default_location = self.env['stock.location'].search([
                        ('branch_id', '=', record.branch_id.id),
                        ('usage', '=', 'internal')  # เงื่อนไข: ใช้ location แบบ internal
                    ], limit=1)
                    print("default_location", default_location.name)
                    if default_location:

                        # sale_order = self.env['sale.order'].search([
                        #     # ('branch_id', '=', picking.branch_id.id),
                        #     ('name', '=', record.origin)
                        # ], limit=1)
                        # # print("sale_order.end_rent_date", sale_order.end_rent_date)
                        # # print("record.end_x_date", record.end_x_date)
                        #
                        # if record.end_x_date and sale_order.end_rent_date != record.end_x_date:
                        #     record.end_x_date = sale_order.end_rent_date

                        for move_line in record.move_line_ids:
                            # ตรวจสอบว่าต้องอัพเดท location_id หรือไม่

                            # ✅ เช็คว่า record.name มีคำว่า "อิน"
                            if "OUT" in record.name.upper():  # แปลงเป็นตัวใหญ่ก่อนเช็ค
                                record.location_id = default_location.id
                                # print(f"✅ record.name มีคำว่า 'IN+++++': {record.name}")
                                if move_line.location_id != default_location:

                                    move_line.location_id = default_location.id


        """
        The auto fill button is allowed only in ready state, and the
        picking have pack operations.
        """
        for rec in self:
            rec.action_pack_op_auto_fill_allowed = (
                    rec.state == "assigned" and rec.move_line_ids
            )

    def _check_action_pack_operation_auto_fill_allowed(self):
        if any(not r.action_pack_op_auto_fill_allowed for r in self):
            raise UserError(
                _(
                    "Filling the operations automatically is not possible, "
                    "perhaps the pickings aren't in the right state "
                    "(Partially available or available)."
                )
            )

    def action_pack_operation_auto_fill(self):

        for record in self:

            origin_prefix = record.origin[:2]
            # print("auto_fill origin_prefix", origin_prefix)

            if record.group_id and record.group_id.name:
                group_name = record.group_id.name[:2]
            else:
                group_name = ''

            # print("auto_fill group_id", group_name)

            if group_name == 'SO':
                if record.branch_id:
                    # ค้นหา stock.location ที่สัมพันธ์กับ branch_id ของ picking
                    default_location = self.env['stock.location'].search([
                        ('branch_id', '=', record.branch_id.id),
                        ('usage', '=', 'internal')  # เงื่อนไข: ใช้ location แบบ internal
                    ], limit=1)

                    if default_location:
                        for move_line in record.move_line_ids:
                            if "IN" in record.name.upper():
                                # print("เข้า ", default_location.name)
                                move_line.location_dest_id = default_location.id


            if origin_prefix == 'SR':
                stock_request = self.env['stock.request.order'].search([
                    ('name', '=', record.origin)
                ], limit=1)
                print("**stock_request**", stock_request.location_id)
                default_location = self.env['stock.location'].search([
                    ('id', '=', stock_request.location_id.id)
                ], limit=1)

                print("**default_location**", default_location.name)

                if default_location:
                    record.write({
                        'force_date': fields.Datetime.now(),
                        'branch_id': self.env.user.branch_id.id,
                    })
                    if record.location_dest_id:
                        default_location = record.location_dest_id

                        move_lines = self.env['stock.move'].search([
                            ('picking_id', '=', record.id)
                        ])

                        for move in move_lines:
                            print(f"🔍 ตรวจสอบ Line: {move.product_id.display_name} (Move ID: {move.id})")

                            # ตรวจสอบว่าไม่มี move_line
                            if not move.move_line_ids:
                                print(f"➕ ยังไม่มี move_line สร้างใหม่ให้สินค้า: {move.product_id.display_name}")

                                self.env['stock.move.line'].create({
                                    'move_id': move.id,
                                    'picking_id': record.id,
                                    'product_id': move.product_id.id,
                                    'product_uom_id': move.product_uom.id,
                                    'qty_done': move.product_uom_qty,  # ปริมาณที่ต้องเคลื่อนย้าย

                                    'location_id': default_location.id,
                                    'location_dest_id': record.location_dest_id.id,
                                })
                            else:
                                print(f"✅ มี move_line แล้วสำหรับสินค้า: {move.product_id.display_name}")

                        for move_line in record.move_line_ids:
                            # ตรวจสอบว่าต้องอัพเดท location_id หรือไม่
                            print("record.name********************", move_line.product_id.name)

                            # ✅ เช็คว่า record.name มีคำว่า "อิน"
                            if "IN" in record.name.upper():  # แปลงเป็นตัวใหญ่ก่อนเช็ค
                                print(f"✅ product_id : {move_line.product_id.id}")
                                print(f"✅ product_name : {move_line.product_id.name}")
                                print(f"✅ location_dest_id: {record.location_dest_id.name}")
                                move_line.location_dest_id = record.location_dest_id.id


        print("id", self.group_id)
        sale_order1 = self.env['stock.picking'].search([
            ('group_id', '=',int(self.group_id))
        ], limit=1)


        sale_order = self.env['sale.order'].search([
            ('name', '=', sale_order1.origin)
        ], limit=1)


        print("sale_order1.origin", sale_order1.origin)
        print("sale_order.start_rent_date", sale_order.start_rent_date)
        print("sale_order.end_rent_date", sale_order.end_rent_date)

        # if not self.start_x_date and self.end_x_date:
        #     if sale_order:
        #         print(
        #             f"sale_order.start_rent_date: {sale_order.start_rent_date} sale_order.end_rent_date: {sale_order.end_rent_date}")
        self.start_x_date = sale_order.start_rent_date
        self.end_x_date = sale_order.end_rent_date


        # if not sale_order:
        #     raise UserError(_('วันที่เริ่มต้นการเช่า และ วันที่สิ้นสุดการเช่า ไม่ดึงมาของ {}.').format(self.origin))





        # if not sale_order1:
        #     # raise UserError(_('วันที่เริ่มต้นการเช่า และ วันที่สิ้นสุดการเช่า ไม่ดึงมา ของ  .') % (int(self.group_id),))
        #     raise UserError(_('วันที่เริ่มต้นการเช่า และ วันที่สิ้นสุดการเช่า ไม่ดึงมาของ {}.').format(int(self.group_id)))

        """
        Fill automatically pack operation for products with the following
        conditions:
            - the package is not required, the package is required if the
            the no product is set on the operation.
            - the operation has no qty_done yet.
        """
        self._check_action_pack_operation_auto_fill_allowed()
        operations = self.mapped("move_line_ids")
        operations_to_auto_fill = operations.filtered(
            lambda op: (
                    op.product_id
                    and not op.qty_done
                    and (
                            not op.lots_visible
                            or not op.picking_id.picking_type_id.avoid_lot_assignment
                    )
            )
        )
        for op in operations_to_auto_fill:
            op.qty_done = op.product_uom_qty

