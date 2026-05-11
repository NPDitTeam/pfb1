# sale_order_report_rent.py
from odoo import models, fields, api

class SaleOrderReportRent(models.Model):
    _name = 'sale.order.report.rent'
    _description = 'รายงานใบสั่งขายเฉพาะการเช่า(sale)'

    sale_id = fields.Many2one('sale.order', string='หมายเลข')
    date_order_x = fields.Date(string="วันที่สั่งซื้อ")
    partner_id = fields.Many2one('res.partner', string='ลูกค้า')
    branch_name = fields.Char(string='สาขา')
    amount_total = fields.Float(string='รวม')
    rental_status = fields.Selection([
        ('due_date', 'ครบกำหนด'),
        ('nearly_due', 'ใกล้ครบกำหนด'),
        ('overdue', 'เกินกำหนด'),
        ('in_rent', 'อยู่ระหว่างการเช่า'),
        ('ready', 'ทำราคา'),
        ('done', 'ปิดบิล')
    ], string="สถานะการเช่า")

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if not self.env.context.get('no_recursive_update'):
            self = self.with_context(no_recursive_update=True)
            self.generate_report()
        return super(SaleOrderReportRent, self).search_read(domain, fields, offset, limit, order)

    @api.model
    def generate_report(self):
        self.sudo().search([]).unlink()
        user_branch = self.env.user.branch_id

        if user_branch.name == 'สำนักงานใหญ่':
            sale_orders = self.env['sale.order'].sudo().search([
                ('state', 'not in', ['sent', 'cancel']),
                ('pfb_so_type', '=', 'rent'),
                ('rental_status', '=', 'done'),
                ('name', 'like', 'SO%'),
            ])
        else:
            sale_orders = self.env['sale.order'].sudo().search([
                ('state', 'not in', ['sent', 'cancel']),
                ('pfb_so_type', '=', 'rent'),
                ('rental_status', '=', 'done'),
                ('branch_id', '=', user_branch.id),
                ('name', 'like', 'SO%'),
            ])

        for so in sale_orders:
            self.sudo().create({
                'sale_id': so.id,
                'date_order_x': so.date_order,
                'partner_id': so.partner_id.id,
                'branch_name': so.branch_id.name or '',
                'amount_total': so.amount_total,
                'rental_status': so.rental_status,
            })

