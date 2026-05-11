from odoo import models, fields, api

class RentalProductReport(models.Model):
    _name = 'dev_rental.product.report'
    _description = 'Rental Product Report'

    product_code = fields.Char(string="รหัสสินค้า")
    product_name = fields.Char(string="รายการสินค้า")
    stock_initial = fields.Float(string="สินค้าตั้งต้น")
    stock_available = fields.Float(string="สินค้าคงเหลือ")
    available_quantity = fields.Float(string="สินค้าถูกจอง")
    stock_in = fields.Float(string="สินค้าถูกเช่า")
    stock_out = fields.Float(string="สินค้าปรับหาย")
    damaged_product = fields.Float(string="สินค้าชำรุด")
    rental_price_day = fields.Float(string="ค่าเช่า/วัน")
    rental_price_month = fields.Float(string="ค่าเช่า/เดือน")
    insurance = fields.Float(string="ค่าประกัน")
    sale_penalty = fields.Float(string="ค่าปรับหาย")
    weight = fields.Float(string="น้ำหนัก")
    branch = fields.Char(string="สาขา")
    # location_id = fields.Many2one('stock.location', string="คลังสินค้า")

    # total_rental_value_day = fields.Float(string="มูลค่ารวมค่าเช่า/วัน", compute='_compute_totals')
    # total_insurance_value = fields.Float(string="มูลค่ารวมค่าประกัน", compute='_compute_totals')
    # total_weight = fields.Float(string="น้ำหนักรวม", compute='_compute_totals')

    # @api.model
    # def search(self, args, offset=0, limit=None, order=None, count=False):
    #     if not self.env.context.get('skip_generate_report'):
    #         self = self.with_context(skip_generate_report=True)
    #         self.generate_report_data()
    #     return super(RentalProductReport, self).search(args, offset, limit, order, count)

    def generate_report_data(self):
        # print("22222222222222222222222222222222222")
        # self.env['dev_rental.product.report'].search([]).unlink()
        self.env['dev_rental.product.report'].sudo().with_context(skip_generate_report=True).search([]).unlink()

        user_branch = self.env.user.branch_id
        if not user_branch:
            print("❌ ผู้ใช้ไม่มี branch_id กำหนดไว้")
            return

        # ดึงคลังสินค้าทั้งหมดใน branch
        locations = self.env['stock.location'].search([
            ('branch_id', '=', user_branch.id),
            ('usage', '=', 'internal')
        ])
        location_ids = locations.ids
        # product_tmpl = self.env['product.template'].search([('id', '=', '716')], limit=1)
        product_tmpls = self.env['product.template'].search([('name', 'like', '%(R)')])
        for product_tmpl in product_tmpls:

            product = product_tmpl.product_variant_id

            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', 'in', location_ids),
            ])

            stock_initial = sum(quants.mapped('stock_initial'))
            inventory_quantity = sum(quants.mapped('quantity'))

            available_quantity  = sum(quants.mapped('available_quantity'))

            # ดึงรายการ scrap ที่เสร็จแล้วของสินค้านี้ในคลังของสาขานี้
            scrap_records = self.env['stock.scrap'].search([
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('location_id', 'in', location_ids),

            ])

            # แยกตามประเภท reason code
            stock_out = sum(
                scrap_records.filtered(lambda s: 'สินค้าหาย' in (s.reason_code_id.name or '')).mapped('scrap_qty')
            )

            damaged_product = sum(
                scrap_records.filtered(lambda s: 'สินค้าชำรุด' in (s.reason_code_id.name or '')).mapped('scrap_qty')
            )

            # ดึง stock.move ทั้งหมดที่ปลายทางไม่ใช่ internal
            all_moves = self.env['stock.move'].search([
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('location_id', 'in', location_ids),
                ('location_dest_id.usage', '!=', 'internal'),
            ])

            # 🔍 กรองเฉพาะ move ที่ไปยังลูกค้า
            customer_moves = all_moves.filtered(lambda m: m.location_dest_id.usage == 'customer')
            stock_in = sum(customer_moves.mapped('product_uom_qty'))

            # print("📦 รายการ Incoming Moves ที่ไปยัง 'Partner Locations/Customers':")
            # for move in customer_moves:
            #     print(f"- Move ID: {move.id}")
            #     print(f"  ➤ สินค้า: {move.product_id.display_name}")
            #     print(f"  ➤ จากคลัง: {move.location_id.complete_name}")
            #     print(f"  ➤ ไปยังคลัง: {move.location_dest_id.complete_name}")
            #     print(f"  ➤ จำนวน: {move.product_uom_qty}")
            #     print(f"  ➤ วันที่: {move.date}")
            #     print("----------")

            product_pricelist_monthly_rate = self.env['product.pricelist'].search([
                ('pricelist_branch_id', '=', user_branch.id),
                ('name', '=', 'เรทเดือน')
            ], limit=1)

            product_pricelist_item_monthly_rate = self.env['product.pricelist.item'].search([
                ('pricelist_id', '=', product_pricelist_monthly_rate.id),
                ('branch_id', '=', user_branch.id),
                ('product_tmpl_id', '=', product_tmpl.id),

            ])

            rental_price_month = sum(product_pricelist_item_monthly_rate.mapped('fixed_price'))

            product_pricelist_one_rate = self.env['product.pricelist'].search([
                ('pricelist_branch_id', '=', user_branch.id),
                ('name', '=', 'เรทวัน')
            ], limit=1)

            # print("product_pricelist_one_rate", product_pricelist_one_rate.id)
            # print("branch_id", user_branch.id)
            # print("product_tmpl", product_tmpl.id)
            product_pricelist_item_one_rate = self.env['product.pricelist.item'].search([
                ('pricelist_id', '=', product_pricelist_one_rate.id),
                ('branch_id', '=', user_branch.id),
                ('product_tmpl_id', '=', product_tmpl.id),

            ], limit=1)
            rental_price_one = sum(product_pricelist_item_one_rate.mapped('fixed_price'))
            pfb_insurance_price = sum(product_pricelist_item_one_rate.mapped('pfb_insurance_price'))

            # print(f"🧾 รายการ: {product_tmpl.name} ({product_tmpl.default_code})")
            # print(f"📦 คงเหลือ = {inventory_quantity}")
            # print(f"📥 สินค้าถูกจอง = {available_quantity}")
            # print(f"📥 สินค้าตั้งต้น = {stock_initial}")
            # print(f"📤 สินค้าหาย = {stock_out}")
            # print(f"📤 สินค้าชำรุด = {damaged_product}")
            # print(f"📤 สินค้าถูกเช่า = {stock_in}")
            # print(f"📤 เรทวัน = {rental_price_one}")
            # print(f"📤 เรทเดือน = {rental_price_month}")
            # print(f"📤 ค่าประกัน = {pfb_insurance_price}")
            # print(f"📤 ค่าปรับหาย = {product_tmpl.list_price}")

            self.create({
                'product_code': product_tmpl.default_code or '',
                'product_name': product_tmpl.name,
                'stock_initial': stock_initial,  # ✅ แก้ตรงนี้: แสดงสินค้าถูกเช่า = ตั้งต้น
                'stock_available': inventory_quantity,
                'available_quantity': available_quantity,
                'stock_in': stock_in,  # ✅ แก้ตรงนี้: แสดงสินค้าตั้งต้น = สินค้าถูกเช่า
                'stock_out': stock_out,
                'damaged_product': damaged_product,
                'rental_price_day': rental_price_one,
                'rental_price_month': rental_price_month,
                'insurance': pfb_insurance_price,
                'sale_penalty': product_tmpl.list_price,
                'weight': product_tmpl.weight,
                'branch': user_branch.name,
                # 'location_id': quants[0].location_id.id if quants else False,
            })
