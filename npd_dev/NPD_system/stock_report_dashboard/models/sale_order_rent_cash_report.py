from odoo import models, fields, api

class SaleOrderRentCashReport(models.Model):
    _name = 'sale.order.rent.cash.report'
    _description = 'รายงานยอดถือเงินสดจากใบเช่า'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', store=True)
    sale_order_name = fields.Char(string='Sale Order Name', store=True)
    branch_id = fields.Many2one('res.branch', string='Branch', store=True)

    branch_display_name = fields.Char(string='Branch Name', store=True)
    customer_id = fields.Many2one('res.partner', string='Customer')
    cash = fields.Char(string='Cash Status', store=True)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if not self.env.context.get('no_recursive_update'):
            self.with_context(no_recursive_update=True).generate_report()
        return super(SaleOrderRentCashReport, self).search_read(domain, fields, offset, limit, order)

    @api.model
    def generate_report(self):
        self.sudo().search([]).unlink()

        user_branch_id = self.env.user.branch_id.id

        payment_invoices = self.env['account.payment.invoice'].sudo().search([
            ('payment_id.payment_method_one_id.name', '=', 'เงินสด')
        ])

        # ดึงชื่อ origin ออกมา
        origin_names = payment_invoices.mapped('origin')

        sale_orders = self.env['sale.order'].sudo().search([
            ('state', 'not in', ('draft', 'sent', 'cancel')),
            ('pfb_so_type', '=', 'rent'),
            ('name', 'like', 'SO%'),
            ('id', '!=', False),
            ('name', 'in', origin_names),
            # ('branch_id', '=', user_branch_id),  # ถ้าอยากกรองเฉพาะสาขาเพิ่มบรรทัดนี้
        ])

        for order in sale_orders:
            cash_status = ''
            total_amount = 0.0
            has_payment = False
            all_returned = True

            payment_lines = self.env['account.payment.invoice'].sudo().search([
                ('origin', '=', order.name),
            ])

            for pl in payment_lines:
                payment = pl.payment_id
                if not payment:
                    continue
                if payment.payment_method_one_id.name == 'เงินสด':
                    has_payment = True
                    if payment.cash_status != 'returned':
                        all_returned = False
                        total_amount += payment.amount

            if has_payment:
                if all_returned and payment_lines:
                    cash_status = 'คืนแล้ว'
                elif total_amount > 0:
                    cash_status = "{:,.2f}".format(total_amount)
            # print("order.id",order.branch_id.id)
            # print("order.id", order.branch_id.name)
            self.env['sale.order.rent.cash.report'].sudo().create({
                'sale_order_id': order.id,
                'sale_order_name': order.name or '',
                'branch_id': order.branch_id.id,
                'branch_display_name': order.branch_id.name or '',
                'customer_id': order.partner_id.id,
                'cash': cash_status,
            })
