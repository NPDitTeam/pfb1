from odoo import models, fields, api


class SaleOrderReportInvoiceDetailBranch(models.Model):
    _name = 'sale.order.report.invoice.detail.branch'
    _description = 'รายงานใบแจ้งหนี้ค้างชำระ รายสาขา รายลูกค้า'
    _order = 'due_date desc, branch_name'
    _rec_name = 'sale_id'

    branch_name = fields.Char(string='สาขา', index=True)
    due_date = fields.Date(string='วันที่ครบกำหนด', index=True)
    sale_id = fields.Many2one('sale.order', string='เลขที่ SO', ondelete='cascade')
    partner_name = fields.Char(string='ชื่อลูกค้า')
    due_amount = fields.Float(string='ยอดค้างชำระ', digits=(12, 2))
    paid_date = fields.Date(string='วันที่ชำระล่าสุด')
    paid_amount = fields.Float(string='ยอดที่ชำระแล้ว', digits=(12, 2))
    user_name = fields.Char(string='ผู้รับผิดชอบ')

    # ลบ search_read override ออกทั้งหมด
    # ลบ generate_report ออก (ย้ายไป wizard แล้ว)