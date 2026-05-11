from odoo import models, fields, api
from datetime import datetime, timedelta


class SaleOrderReportInvoiceWizard(models.TransientModel):
    _name = 'sale.order.report.invoice.wizard'
    _description = 'Wizard สำหรับรายงานใบแจ้งหนี้ค้างชำระ'

    date_from = fields.Date(
        string='วันที่เริ่มต้น',
        help='เว้นว่างเพื่อดูข้อมูลทั้งหมด'
    )
    date_to = fields.Date(
        string='วันที่สิ้นสุด',
        default=fields.Date.today,
        help='เว้นว่างเพื่อดูข้อมูลทั้งหมด'
    )
    branch_ids = fields.Many2many(
        'res.branch',
        string='สาขา',
        help='เว้นว่างเพื่อดูทุกสาขา'
    )
    show_only_due = fields.Boolean(
        string='แสดงเฉพาะที่ค้างชำระ',
        default=True,
        help='แสดงเฉพาะรายการที่มียอดค้างชำระมากกว่า 0'
    )

    def action_generate_report(self):
        """สร้างรายงานตามเงื่อนไขที่เลือก"""
        # แสดง loading
        self.env.cr.commit()

        # ลบข้อมูลเก่าทั้งหมด
        self.env['sale.order.report.invoice.detail.branch'].sudo().search([]).unlink()

        # สร้าง domain สำหรับค้นหา Sale Orders
        domain = [
            ('state', 'not in', ['sent', 'cancel']),
            ('contact_type', '=', 'branch'),
            ('name', 'like', 'SO%'),
        ]

        # เพิ่มเงื่อนไขวันที่ถ้ามี
        if self.date_from:
            domain.append(('date_order', '>=', self.date_from))
        if self.date_to:
            # เพิ่ม 1 วันเพื่อให้รวมทั้งวันสุดท้าย
            date_to_end = self.date_to + timedelta(days=1)
            domain.append(('date_order', '<', date_to_end))

        # เพิ่มเงื่อนไขสาขาถ้ามี
        if self.branch_ids:
            domain.append(('branch_id', 'in', self.branch_ids.ids))

        # ค้นหา Sale Orders
        sale_orders = self.env['sale.order'].sudo().search(domain)

        # เตรียมข้อมูลที่จะสร้าง
        records_to_create = []
        report_model = self.env['sale.order.report.invoice.detail.branch']

        # วนลูปสร้างข้อมูล
        for so in sale_orders:
            # ค้นหา Invoices ที่เกี่ยวข้อง
            invoice_domain = [
                ('invoice_origin', '=', so.name),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),  # เฉพาะที่ posted แล้ว
            ]

            # ถ้ามีเงื่อนไขวันที่ ให้ filter invoice ด้วย
            if self.date_from:
                invoice_domain.append(('invoice_date', '>=', self.date_from))
            if self.date_to:
                invoice_domain.append(('invoice_date', '<=', self.date_to))

            invoices = self.env['account.move'].sudo().search(invoice_domain)

            for inv in invoices:
                due_amount = inv.amount_residual or 0.0

                # ถ้าเลือกแสดงเฉพาะที่ค้างชำระ และยอดค้างเป็น 0 ให้ข้าม
                if self.show_only_due and due_amount <= 0.0:
                    continue

                paid_amount = 0.0
                paid_date = None

                # คำนวณยอดที่จ่ายแล้ว - เฉพาะการชำระที่วันที่ไม่ตรงกับ invoice_date
                if inv.payment_state in ['paid', 'partial']:
                    paid_amount, paid_date = self._get_paid_amount_and_date(inv)

                # เตรียมข้อมูลสำหรับสร้าง record
                records_to_create.append({
                    'branch_name': so.branch_id.name if so.branch_id else 'ไม่ระบุสาขา',
                    'due_date': inv.invoice_date_due or inv.invoice_date,
                    'sale_id': so.id,
                    'partner_name': so.partner_id.name,
                    'due_amount': due_amount,
                    'paid_date': paid_date,
                    'paid_amount': paid_amount,
                    'user_name': so.sales_contact.name if so.sales_contact else so.user_id.name,
                })

        # สร้างข้อมูลทั้งหมดในครั้งเดียว (เร็วกว่า)
        if records_to_create:
            report_model.sudo().create(records_to_create)

        # ✅ แก้ไขส่วนนี้ - เปิดหน้า Tree View แสดงผลลัพธ์
        action = {
            'type': 'ir.actions.act_window',
            'name': f'รายงานใบแจ้งหนี้ค้างชำระ(สาขา) - พบ {len(records_to_create)} รายการ',
            'res_model': 'sale.order.report.invoice.detail.branch',
            'view_mode': 'tree,pivot,graph',
            'target': 'current',
        }

        # ✅ ลองหา view ID ที่ถูกต้อง
        try:
            # ลองใช้ชื่อโมดูลที่ถูกต้อง
            tree_view = self.env.ref('stock_report_dashboard.view_tree_sale_order_report_invoice_detail_branch', False)
            if tree_view:
                action['views'] = [
                    (tree_view.id, 'tree'),
                    (False, 'pivot'),
                    (False, 'graph'),
                ]
        except:
            # ถ้าหาไม่เจอก็ไม่ต้องระบุ views (ใช้ default)
            pass

        # เพิ่ม context ถ้าต้องการ
        action['context'] = {'search_default_has_due': 1}

        return action

    def _get_last_payment_date(self, invoice):
        """หาวันที่จ่ายเงินล่าสุดของ Invoice"""
        payment_dates = []

        try:
            # ตรวจสอบ reconciled entries
            for line in invoice.line_ids.filtered(
                    lambda l: l.account_id.user_type_id.type in ('receivable', 'payable')):
                for partial in line.matched_debit_ids:
                    if partial.debit_move_id.payment_id:
                        payment_dates.append(partial.debit_move_id.payment_id.date)
                    elif partial.debit_move_id.date:
                        payment_dates.append(partial.debit_move_id.date)

                for partial in line.matched_credit_ids:
                    if partial.credit_move_id.payment_id:
                        payment_dates.append(partial.credit_move_id.payment_id.date)
                    elif partial.credit_move_id.date:
                        payment_dates.append(partial.credit_move_id.date)
        except:
            pass

        # คืนค่าวันที่ล่าสุด
        return max(payment_dates) if payment_dates else None