from odoo import models, fields, api


class StockReportWizard(models.TransientModel):
    _name = 'stock.report.wizard'
    _description = 'Wizard สำหรับสร้างรายงานสินค้าเช่า'

    branch_ids = fields.Many2many(
        'res.branch',
        string='สาขา',
        help='เลือกสาขาที่ต้องการดูรายงาน (เว้นว่างเพื่อดูทุกสาขา)'
    )

    product_ids = fields.Many2many(
        'product.template',
        string='สินค้า',
        domain=[('name', 'like', '%(R)')],
        help='เลือกสินค้าที่ต้องการดูรายงาน (เว้นว่างเพื่อดูทั้งหมด)'
    )

    filter_type = fields.Selection([
        ('all', 'แสดงทั้งหมด'),
        ('available', 'เฉพาะสินค้าที่มีคงเหลือ'),
        ('rented', 'เฉพาะสินค้าที่ถูกเช่า'),
        ('damaged', 'เฉพาะสินค้าที่มีชำรุด/หาย')
    ], string='ประเภทการแสดง', default='all')

    def action_generate_report(self):
        """สร้างรายงานตามเงื่อนไขที่เลือก"""
        # ลบข้อมูลเก่า
        self.env['dev_rental.product.report'].sudo().search([]).unlink()

        # ✅ ถ้าไม่เลือกสาขา ให้แสดงทุกสาขา
        if self.branch_ids:
            branches = self.branch_ids
        else:
            # ค้นหาทุกสาขา
            branches = self.env['res.branch'].search([])

            # ถ้าไม่มีสาขาในระบบเลย
            if not branches:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'คำเตือน',
                        'message': 'ไม่พบสาขาในระบบ',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

        # วนลูปสร้างรายงานแต่ละสาขา
        records_created = 0
        for branch in branches:
            count = self._generate_branch_report(branch)
            records_created += count

        # ถ้าไม่มีข้อมูลเลย
        if records_created == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'แจ้งเตือน',
                    'message': 'ไม่พบข้อมูลตามเงื่อนไขที่กำหนด',
                    'type': 'info',
                    'sticky': False,
                }
            }

        # เปิดหน้า Tree View
        action = {
            'type': 'ir.actions.act_window',
            'name': f'รายงานสินค้าเช่า - พบ {records_created} รายการ จาก {len(branches)} สาขา',
            'res_model': 'dev_rental.product.report',
            'view_mode': 'tree,pivot,graph',
            'target': 'current',
        }

        # เพิ่ม domain ถ้ามีการกรอง
        domain = []
        if self.filter_type == 'available':
            domain.append(('stock_available', '>', 0))
        elif self.filter_type == 'rented':
            domain.append(('stock_in', '>', 0))
        elif self.filter_type == 'damaged':
            domain.append('|')
            domain.append(('stock_out', '>', 0))
            domain.append(('damaged_product', '>', 0))

        if domain:
            action['domain'] = domain

        return action

    def _generate_branch_report(self, branch):
        """สร้างรายงานสำหรับสาขาที่ระบุ"""
        # ดึงคลังสินค้าในสาขา
        locations = self.env['stock.location'].search([
            ('branch_id', '=', branch.id),
            ('usage', '=', 'internal')
        ])
        location_ids = locations.ids

        # ถ้าไม่มีคลังในสาขานี้ ให้ข้าม
        if not location_ids:
            return 0

        # กำหนดสินค้าที่จะรายงาน
        if self.product_ids:
            product_tmpls = self.product_ids
        else:
            product_tmpls = self.env['product.template'].search([('name', 'like', '%(R)')])

        records_created = 0

        # วนลูปสร้างรายงานแต่ละสินค้า
        for product_tmpl in product_tmpls:
            product = product_tmpl.product_variant_id

            # ดึงข้อมูล stock quant
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', 'in', location_ids),
            ])

            # ถ้าไม่มี quant และเลือกดูเฉพาะที่มีคงเหลือ ให้ข้าม
            if not quants and self.filter_type == 'available':
                continue

            stock_initial = sum(quants.mapped('stock_initial'))
            inventory_quantity = sum(quants.mapped('quantity'))
            available_quantity = sum(quants.mapped('available_quantity'))

            # ดึงข้อมูล scrap
            scrap_records = self.env['stock.scrap'].search([
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('location_id', 'in', location_ids),
            ])

            stock_out = sum(
                scrap_records.filtered(lambda s: 'สินค้าหาย' in (s.reason_code_id.name or '')).mapped('scrap_qty')
            )

            damaged_product = sum(
                scrap_records.filtered(lambda s: 'สินค้าชำรุด' in (s.reason_code_id.name or '')).mapped('scrap_qty')
            )

            # ดึง stock move ไปยังลูกค้า
            customer_moves = self.env['stock.move'].search([
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('location_id', 'in', location_ids),
                ('location_dest_id.usage', '=', 'customer'),
            ])
            stock_in = sum(customer_moves.mapped('product_uom_qty'))

            # ตรวจสอบตามประเภทการแสดง
            if self.filter_type == 'rented' and stock_in == 0:
                continue
            if self.filter_type == 'damaged' and stock_out == 0 and damaged_product == 0:
                continue

            # ดึงข้อมูล pricelist
            rental_price_month = 0
            rental_price_day = 0
            pfb_insurance_price = 0

            # Pricelist เรทเดือน
            pricelist_monthly = self.env['product.pricelist'].search([
                ('pricelist_branch_id', '=', branch.id),
                ('name', '=', 'เรทเดือน')
            ], limit=1)

            if pricelist_monthly:
                item_monthly = self.env['product.pricelist.item'].search([
                    ('pricelist_id', '=', pricelist_monthly.id),
                    ('branch_id', '=', branch.id),
                    ('product_tmpl_id', '=', product_tmpl.id),
                ], limit=1)
                rental_price_month = item_monthly.fixed_price if item_monthly else 0

            # Pricelist เรทวัน
            pricelist_daily = self.env['product.pricelist'].search([
                ('pricelist_branch_id', '=', branch.id),
                ('name', '=', 'เรทวัน')
            ], limit=1)

            if pricelist_daily:
                item_daily = self.env['product.pricelist.item'].search([
                    ('pricelist_id', '=', pricelist_daily.id),
                    ('branch_id', '=', branch.id),
                    ('product_tmpl_id', '=', product_tmpl.id),
                ], limit=1)
                if item_daily:
                    rental_price_day = item_daily.fixed_price
                    pfb_insurance_price = item_daily.pfb_insurance_price

            # สร้างรายงาน
            self.env['dev_rental.product.report'].create({
                'product_code': product_tmpl.default_code or '',
                'product_name': product_tmpl.name,
                'stock_initial': stock_initial,
                'stock_available': inventory_quantity,
                'available_quantity': available_quantity,
                'stock_in': stock_in,
                'stock_out': stock_out,
                'damaged_product': damaged_product,
                'rental_price_day': rental_price_day,
                'rental_price_month': rental_price_month,
                'insurance': pfb_insurance_price,
                'sale_penalty': product_tmpl.list_price,
                'weight': product_tmpl.weight,
                'branch': branch.name,
            })

            records_created += 1

        return records_created