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

        # ดึงข้อมูลจาก account.move (invoice) เป็นหลัก
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),  # เฉพาะสถานะลงบันทึกเท่านั้น
            ('payment_state', 'in', ['not_paid', 'partial']),
        ]

        # if user_branch.name != 'สำนักงานใหญ่':
        #     domain.append(('partner_id.branch_id', '=', user_branch.id))

        invoices = self.env['account.move'].sudo().search(domain)

        for inv in invoices:
            # ค้นหา sale_order จาก invoice
            so = self.env['sale.order'].sudo().search([
                ('name', '=', inv.invoice_origin),
                ('contact_type', '=', 'sale'),
            ], limit=1)
            if so:
                due_amount = inv.amount_residual or 0.0

                if due_amount == 0.0:
                    continue  # ❌ ข้ามถ้ายอดค้างชำระเป็น 0

                paid_amount = 0.0
                payment_dates = []

                # รวบรวมข้อมูลการชำระจาก matched_debit_ids และ matched_credit_ids
                for line in inv.line_ids:
                    if line.matched_debit_ids:
                        for partial in line.matched_debit_ids:
                            if partial.debit_move_id.payment_id:
                                payment_date = partial.debit_move_id.payment_id.date
                                # ตรวจสอบว่าวันที่ชำระไม่ตรงกับ invoice_date
                                if payment_date != inv.invoice_date:
                                    paid_amount += partial.amount or 0.0
                                    payment_dates.append(payment_date)
                    elif line.matched_credit_ids:
                        for partial in line.matched_credit_ids:
                            if partial.credit_move_id.payment_id:
                                payment_date = partial.credit_move_id.payment_id.date
                                # ตรวจสอบว่าวันที่ชำระไม่ตรงกับ invoice_date
                                if payment_date != inv.invoice_date:
                                    paid_amount += partial.amount or 0.0
                                    payment_dates.append(payment_date)

                # กำหนด paid_date เป็นวันที่ชำระล่าสุด
                paid_date = None
                if payment_dates:
                    paid_date = max(payment_dates)

                self.sudo().create({
                    'branch_name': so.branch_id.name or inv.partner_id.branch_id.name or '',
                    'due_date': inv.invoice_date,
                    'sale_id': so.id if so else None,
                    'partner_name': inv.partner_id.name,
                    'due_amount': due_amount,
                    'paid_date': paid_date,
                    'paid_amount': paid_amount,
                    'user_name': so.sales_contact.name if so else '',
                })
