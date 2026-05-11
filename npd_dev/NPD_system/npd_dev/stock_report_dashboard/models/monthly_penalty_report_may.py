from odoo import models, fields, api


class MonthlyPenaltyReport(models.Model):
    _name = 'monthly.penalty.report.may'
    _description = 'สรุปรายงานหนี้ค้างชำระ'
    _order = 'report_date desc'

    report_date = fields.Date(string='วดป')
    
    # ฟิลด์ for SO reference
    sale_order_ids = fields.One2many(
        'sale.order',
        compute='_compute_sale_orders',
        string='ใบสั่งซื้อเช่า',
        help='ใบสั่งซื้อเช่าที่ใช้ในการสรุปรายงาน'
    )
    
    so_number = fields.Char(
        string='เลขที่ SO',
        help='เลขที่ใบสั่งซื้อเช่า'
    )
    
    branch_id = fields.Many2one(
        'res.branch',
        string='สาขา',
        compute='_compute_branch',
        help='สาขาจากใบสั่งซื้อเช่า'
    )
    
    rental_amount = fields.Float(string='ค่าเช่าสินค้า')
    # vat = fields.Float(string='VAT')
    insurance = fields.Float(string='ค่าประกัน')
    damage_penalty = fields.Float(string='ค่าปรับชำรุด')
    lost_penalty = fields.Float(string='ค่าปรับหาย')
    rental_discount = fields.Float(string='ส่วนลดค่าเช่า')
    line_discount = fields.Float(string='ส่วนลดปรับหาย')
    net_rental_fee = fields.Float(string='ค่าเช่าสุทธิ')

    rental_payment_amount = fields.Float(string="รับชำระหนี้ค่าเช่า")
    vat_rental_payment_amount = fields.Float(string="VAT")
    lost_payment_amount = fields.Float(string="รับชำระหนี้ค่าปรับหาย")
    damaged_payment_amount = fields.Float(string="รับชำระหนี้ค่าปรับชำรุด")

    rental_unpaid_amount = fields.Float(string="ค้างชำระค่าเช่า")
    vat_rental_unpaid_amount = fields.Float(string="ค้าง VAT")
    lost_unpaid_amount = fields.Float(string="ค้างชำระค่าปรับหาย")
    damaged_unpaid_amount = fields.Float(string="ค้างชำระค่าปรับชำรุด")
    difference = fields.Float(string="ส่วนต่าง")
    customer_code = fields.Char(string="รหัสลูกค้า")
    customer_name = fields.Char(string="ชื่อลูกค้า")

    # Store SO IDs for reference (hidden field)
    so_names = fields.Char(string='SO IDs', help='รายการ ID ของใบสั่งซื้อ')

    def _compute_sale_orders(self):
        """ดึงข้อมูล SO จาก so_names (stored SO IDs)"""
        for record in self:
            if record.so_names:
                try:
                    # so_names เก็บ SO IDs (เช่น "123,456,789")
                    so_ids_list = [int(id_str.strip()) for id_str in record.so_names.split(',') if id_str.strip().isdigit()]
                    if so_ids_list:
                        sale_orders = self.env['sale.order'].search([
                            ('id', 'in', so_ids_list)
                        ])
                        record.sale_order_ids = sale_orders
                    else:
                        record.sale_order_ids = False
                except:
                    record.sale_order_ids = False
            else:
                record.sale_order_ids = False

    def _compute_branch(self):
        """ดึงข้อมูลสาขาจาก SO"""
        for record in self:
            if record.sale_order_ids:
                # ดึงสาขาจาก SO แรก (สมมติว่าทั้งหมดมาจากสาขาเดียวกัน)
                record.branch_id = record.sale_order_ids[0].branch_id.id if record.sale_order_ids[0].branch_id else False
            else:
                record.branch_id = False
