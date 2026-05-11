from odoo import models, fields, api

class SaleOrderReportInvoiceDetail(models.Model):
    _name = 'sale.order.report.invoice.detail'
    _description = 'รายงานใบแจ้งหนี้ค้างชำระ รายsals รายลูกค้า'
    _order = 'due_date desc'

    branch_name = fields.Char(string='สาขา')
    due_date = fields.Date(string='วันที่ค้างชำระ')
    sale_id = fields.Many2one('sale.order', string='เลขที่เอกสาร')
    partner_name = fields.Char(string='ชื่อลูกค้า')
    due_amount = fields.Float(string='ยอดค้างชำระ')
    paid_date = fields.Date(string='วันที่ชำระ')
    paid_amount = fields.Float(string='ยอดรับชำระ')
    user_name = fields.Char(string='ผู้รับผิดชอบ')

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if not self.env.context.get('no_recursive_update'):
            self = self.with_context(no_recursive_update=True)
            self.generate_report()
        return super().search_read(domain, fields, offset, limit, order)

    @api.model
    def generate_report(self):
        self.sudo().search([]).unlink()
        user_branch = self.env.user.branch_id

        if user_branch.name == 'สำนักงานใหญ่':
            sale_orders = self.env['sale.order'].sudo().search([
                ('state', 'not in', ['sent', 'cancel']),
                ('contact_type', '=', 'sale'),
                ('name', 'like', 'SO%'),
            ])
        else:
            sale_orders = self.env['sale.order'].sudo().search([
                ('state', 'not in', ['sent', 'cancel']),
                ('branch_id', '=', user_branch.id),
                ('contact_type', '=', 'sale'),
                ('name', 'like', 'SO%'),
            ])

        for so in sale_orders:
            invoices = self.env['account.move'].sudo().search([
                ('invoice_origin', '=', so.name),
                ('move_type', '=', 'out_invoice'),
            ])

            for inv in invoices:
                due_amount = inv.amount_residual or 0.0
                paid_amount = 0.0
                paid_date = None

                if due_amount == 0.0:
                    continue  # ❌ ข้ามถ้ายอดค้างชำระเป็น 0

                if inv.payment_state in ['not_paid', 'partial']:
                    paid_amount = inv.amount_total
                    for line in inv.line_ids:
                        if line.matched_debit_ids:
                            for partial in line.matched_debit_ids:
                                if partial.debit_move_id.payment_id:
                                    paid_date = partial.debit_move_id.payment_id.date
                                    break
                        elif line.matched_credit_ids:
                            for partial in line.matched_credit_ids:
                                if partial.credit_move_id.payment_id:
                                    paid_date = partial.credit_move_id.payment_id.date
                                    break

                self.sudo().create({
                    'branch_name': so.branch_id.name or '',
                    'due_date': inv.invoice_date,
                    'sale_id': so.id,
                    'partner_name': so.partner_id.name,
                    'due_amount': due_amount,
                    'paid_date': paid_date,
                    'paid_amount': paid_amount,
                    'user_name': so.sales_contact.name,
                })
