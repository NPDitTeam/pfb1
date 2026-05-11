from odoo import models, api, fields
from odoo.exceptions import UserError

class StockCutConfirmWizard(models.TransientModel):
    _name = 'stock.cut.confirm.wizard'
    _description = 'Confirm Stock Cut Wizard'

    order_id = fields.Many2one('sale.order', string='Sale Order')
    confirm_line_ids = fields.One2many('stock.cut.confirm.line', 'wizard_id', string='Stock Moves to Confirm')

    @api.model
    def default_get(self, fields_list):
        print("🔥 [DEBUG] default_get started for StockCutConfirmWizard")
        res = super().default_get(fields_list)

        order_id = self.env.context.get('default_order_id')
        print("🧾 default_order_id from context:", order_id)

        if order_id:
            order = self.env['sale.order'].browse(order_id)
            lines = []

            # ✅ ค้นหา stock.location ที่มี branch_id ตรงกับ order.branch_id
            location = self.env['stock.location'].search([
                ('branch_id', '=', order.branch_id.id),
                ('usage', '=', 'internal')  # ดึงเฉพาะตำแหน่งภายใน
            ], limit=1)

            location_name = location.display_name if location else "ไม่พบคลังของสาขา"
            print("📦 ตำแหน่งคลังของสาขา:", location_name)

            for line in order.order_line:
                if line.pfb_quantity > 0:
                    lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'quantity': line.pfb_quantity,
                        'location_name': location_name,
                    }))
                    print(f"✅ Add line: {line.product_id.display_name} = {line.pfb_quantity} at {location_name}")

            res['order_id'] = order.id
            res['confirm_line_ids'] = lines

        return res

    def confirm_stock_cut(self):
        pickings = self.order_id.picking_ids.filtered(lambda p: p.state != 'cancel').sorted('id', reverse=True)

        if not pickings:
            raise UserError("❌ ไม่พบใบจัดส่งสำหรับคำสั่งขายนี้")

        picking = pickings[0]

        # ✅ ตั้งค่า start_x_date จาก order
        if self.order_id.start_rent_date:
            picking.write({'start_x_date': self.order_id.start_rent_date})
            print("🕓 ตั้งค่า start_x_date =", self.order_id.start_rent_date)

        if self.order_id.end_rent_date:
            picking.write({'end_x_date': self.order_id.end_rent_date})
            print("🕓 ตั้งค่า end_x_date =", self.order_id.end_rent_date)

        if picking.state == 'done':
            raise UserError("📦 ใบจัดส่งนี้ถูกตัดสต๊อกเรียบร้อยแล้ว ไม่สามารถตัดซ้ำได้")


        # ✅ ค้นหา location จาก branch โดยระบุชื่อย่อยให้แม่นยำขึ้น
        location = self.env['stock.location'].search([
            ('branch_id', '=', self.order_id.branch_id.id),
            ('usage', '=', 'internal'),

        ], limit=1)
        if not location:
            raise UserError("❌ ไม่พบคลังต้นทางของสาขา (ย่อย)")

        print("📦 คลังที่ใช้ตัด:", location.complete_name)

        # ✅ บังคับให้ Picking ใช้คลังนี้ด้วย
        if picking.location_id.id != location.id:
            picking.write({'location_id': location.id})
            print("🔁 เปลี่ยน Picking Location →", location.complete_name)

        # ✅ ตรวจสอบ stock ก่อนสร้าง move
        for line in self.confirm_line_ids:
            available_qty = line.product_id.with_context(location=location.id).qty_available
            print(f"🔍 {line.product_id.display_name} - ต้องตัด: {line.quantity}, คงเหลือ: {available_qty}")
            if available_qty < line.quantity:
                raise UserError(
                    f"❌ สินค้า '{line.product_id.display_name}' มีคงเหลือในคลัง {available_qty:.2f} หน่วย "
                    f"ไม่เพียงพอสำหรับตัด {line.quantity:.2f} หน่วย"
                )

        # ✅ ถ้ายังไม่มี move → สร้าง
        if not picking.move_ids_without_package:
            moves = []
            for line in self.confirm_line_ids:
                moves.append((0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': location.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'picking_id': picking.id,
                }))
            picking.write({'move_ids_without_package': moves})
            print("🧱 เพิ่ม stock.move เรียบร้อย")

        # ✅ กำหนด quantity_done และ location_id
        for move in picking.move_ids_without_package:
            line = self.confirm_line_ids.filtered(lambda l: l.product_id.id == move.product_id.id)
            if line:
                move.quantity_done = line[0].quantity
                move.location_id = location.id
                print(f"✔️ ตัด: {move.product_id.display_name} = {move.quantity_done}")
                print(f"📦 Move Location (set): {location.complete_name}")

        # ✅ Validate การตัดสต๊อก
        picking.button_validate()
        print("✅ ตัดสต๊อกเรียบร้อย")

        return {
            'type': 'ir.actions.act_window_close',
            'tag': 'reload',
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ ตัดสต๊อกสำเร็จ',
                'message': f'ใบจัดส่ง {picking.name} ถูกตัดสต๊อกเรียบร้อยแล้ว',
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }






