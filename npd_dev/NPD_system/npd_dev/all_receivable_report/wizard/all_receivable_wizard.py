# -*- coding: utf-8 -*-
from odoo import models, fields, api
from collections import defaultdict


class AllReceivableWizard(models.TransientModel):
    _name = 'all.receivable.wizard'
    _description = 'Wizard สำหรับรายงานลูกหนี้ทั้งหมด'

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

    def _get_shipping_cost_from_so(self, sale_order):
        """ดึงค่าขนส่งจาก Sale Order ตามเงื่อนไข"""
        if not sale_order:
            return 0.0

        # 1. เช็คว่าใช้ค่าขนส่งพิเศษที่เป็น 0 หรือไม่
        if sale_order.use_special_delivery_zero:
            return 0.0
        # 2. เช็ค shipping_cost_m ก่อน ถ้ามีค่าใช้ shipping_cost_m
        elif sale_order.shipping_cost_m and sale_order.shipping_cost_m > 0:
            return sale_order.shipping_cost_m
        # 3. ถ้าไม่มี shipping_cost_m ใช้ shipping_cost
        else:
            return sale_order.shipping_cost or 0.0

    def action_generate_report(self):
        """สร้างรายงานตามเงื่อนไขที่เลือก - Group by ลูกค้า"""
        # ลบข้อมูลเก่าทั้งหมด
        self.env['all.receivable.report'].sudo().search([]).unlink()

        # สร้าง domain สำหรับค้นหา Invoices
        invoice_domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
        ]

        # เพิ่มเงื่อนไขวันที่ถ้ามี
        if self.date_from:
            invoice_domain.append(('invoice_date', '>=', self.date_from))
        if self.date_to:
            invoice_domain.append(('invoice_date', '<=', self.date_to))

        # กรองตามสาขาถ้าเลือก
        if self.branch_ids:
            invoice_domain.append(('branch_id', 'in', self.branch_ids.ids))

        # ค้นหา Invoices
        invoices = self.env['account.move'].sudo().search(invoice_domain)

        # Group by ลูกค้า - ใช้ dict เก็บข้อมูลรวม
        partner_data = defaultdict(lambda: {
            'partner_id': False,
            'partner_code': '',
            'partner_name': '',
            'partner_phone': '-',
            'partner_address': '-',
            'branch_name': '',
            'first_debt_date': False,
            'last_due_date': False,
            'rent_amount': 0.0,
            'insurance_amount': 0.0,
            'lost_penalty_amount': 0.0,
            'damage_penalty_amount': 0.0,
            'shipping_cost_amount': 0.0,
            'vat_amount': 0.0,
            'amount_total': 0.0,
            'amount_residual': 0.0,
            'amount_remaining': 0.0,
            'invoice_count': 0,
            'branches': set(),
            'processed_origins': set(),
        })

        # วนลูปรวมข้อมูลตามลูกค้า
        for inv in invoices:
            partner = inv.partner_id
            partner_key = partner.id

            # สร้างที่อยู่ลูกค้า (เฉพาะครั้งแรก)
            if not partner_data[partner_key]['partner_id']:
                address_parts = []
                if partner.street:
                    address_parts.append(partner.street)
                if partner.street2:
                    address_parts.append(partner.street2)
                if partner.city:
                    address_parts.append(partner.city)
                if partner.state_id:
                    address_parts.append(partner.state_id.name)
                if partner.zip:
                    address_parts.append(partner.zip)
                if partner.country_id:
                    address_parts.append(partner.country_id.name)
                
                partner_data[partner_key]['partner_id'] = partner.id
                partner_data[partner_key]['partner_code'] = partner.ref or str(partner.id)
                partner_data[partner_key]['partner_name'] = partner.name or '-'
                partner_data[partner_key]['partner_phone'] = partner.phone or partner.mobile or '-'
                partner_data[partner_key]['partner_address'] = ', '.join(filter(None, address_parts)) or '-'

            # ดึงชื่อสมุดรายวัน (Journal)
            journal_name = ''
            if inv.journal_id:
                journal_name = inv.journal_id.name or ''

            # ดึงประเภทใบแจ้งหนี้จาก reason_code_id
            reason_name = ''
            if hasattr(inv, 'reason_code_id') and inv.reason_code_id:
                reason_name = inv.reason_code_id.name or ''

            # แยกยอดตามประเภทใบแจ้งหนี้
            inv_untaxed = inv.amount_untaxed or 0.0
            
            # เช็คสมุดรายวันก่อน - ถ้าเป็น "สมุดรายวันค่าประกัน" ให้ไปที่ค่าประกัน
            if 'สมุดรายวันค่าประกัน' in journal_name:
                partner_data[partner_key]['insurance_amount'] += inv_untaxed
            elif 'สินค้าหาย' in reason_name:
                partner_data[partner_key]['lost_penalty_amount'] += inv_untaxed
            elif 'สินค้าชำรุด' in reason_name:
                partner_data[partner_key]['damage_penalty_amount'] += inv_untaxed
            else:
                partner_data[partner_key]['rent_amount'] += inv_untaxed

            # ดึงค่าขนส่งจาก Sale Order (ผ่าน invoice_origin)
            invoice_origin = inv.invoice_origin or ''
            if invoice_origin and invoice_origin not in partner_data[partner_key]['processed_origins']:
                sale_order = self.env['sale.order'].sudo().search([
                    ('name', '=', invoice_origin)
                ], limit=1)
                
                if sale_order:
                    shipping_cost = self._get_shipping_cost_from_so(sale_order)
                    partner_data[partner_key]['shipping_cost_amount'] += shipping_cost
                    partner_data[partner_key]['processed_origins'].add(invoice_origin)

            # รวม VAT และยอดรวม
            partner_data[partner_key]['vat_amount'] += inv.amount_tax or 0.0
            partner_data[partner_key]['amount_total'] += inv.amount_total or 0.0
            partner_data[partner_key]['amount_residual'] += inv.amount_residual or 0.0
            partner_data[partner_key]['invoice_count'] += 1

            # เก็บสาขา
            branch_name = inv.branch_id.name if hasattr(inv, 'branch_id') and inv.branch_id else 'ไม่ระบุสาขา'
            partner_data[partner_key]['branches'].add(branch_name)

            # เก็บวันที่เริ่มเป็นหนี้ และ วันครบกำหนดชำระ
            invoice_date = inv.invoice_date
            invoice_date_due = inv.invoice_date_due or inv.invoice_date
            
            if invoice_date:
                if not partner_data[partner_key]['first_debt_date']:
                    partner_data[partner_key]['first_debt_date'] = invoice_date
                elif invoice_date < partner_data[partner_key]['first_debt_date']:
                    partner_data[partner_key]['first_debt_date'] = invoice_date
            
            if invoice_date_due:
                if not partner_data[partner_key]['last_due_date']:
                    partner_data[partner_key]['last_due_date'] = invoice_date_due
                elif invoice_date_due > partner_data[partner_key]['last_due_date']:
                    partner_data[partner_key]['last_due_date'] = invoice_date_due

        # เตรียมข้อมูลที่จะสร้าง
        records_to_create = []
        report_model = self.env['all.receivable.report']

        for partner_key, data in partner_data.items():
            # คำนวณยอดรวมจากฟิลด์ต่างๆ (ไม่รวมหัก ณ ที่จ่าย)
            calculated_total = (
                data['rent_amount'] +
                data['insurance_amount'] +
                data['lost_penalty_amount'] +
                data['damage_penalty_amount'] +
                data['shipping_cost_amount'] +
                data['vat_amount']
            )

            # คำนวณคงเหลือ = ยอดรวม - ยอดค้างชำระ
            amount_remaining = calculated_total - data['amount_residual']
            
            # แก้ปัญหาการปัดเศษ
            if abs(amount_remaining) < 1.0:
                amount_remaining = 0.0
                calculated_total = data['amount_residual']
            
            records_to_create.append({
                'partner_id': data['partner_id'],
                'partner_code': data['partner_code'],
                'partner_name': data['partner_name'],
                'partner_phone': data['partner_phone'],
                'partner_address': data['partner_address'],
                'branch_name': ', '.join(sorted(data['branches'])),
                'first_debt_date': data['first_debt_date'],
                'last_due_date': data['last_due_date'],
                'rent_amount': data['rent_amount'],
                'insurance_amount': data['insurance_amount'],
                'lost_penalty_amount': data['lost_penalty_amount'],
                'damage_penalty_amount': data['damage_penalty_amount'],
                'shipping_cost_amount': data['shipping_cost_amount'],
                'vat_amount': data['vat_amount'],
                'amount_total': calculated_total,
                'amount_residual': data['amount_residual'],
                'amount_remaining': amount_remaining,
                'invoice_count': data['invoice_count'],
            })

        # สร้างข้อมูลทั้งหมด
        if records_to_create:
            report_model.sudo().create(records_to_create)

        # เปิดหน้า Tree View แสดงผลลัพธ์
        action = {
            'type': 'ir.actions.act_window',
            'name': f'รายงานลูกหนี้ทั้งหมด - พบ {len(records_to_create)} ราย',
            'res_model': 'all.receivable.report',
            'view_mode': 'tree,pivot,graph',
            'target': 'current',
        }

        try:
            tree_view = self.env.ref('all_receivable_report.view_tree_all_receivable_report', False)
            if tree_view:
                action['views'] = [
                    (tree_view.id, 'tree'),
                    (False, 'pivot'),
                    (False, 'graph'),
                ]
        except:
            pass

        return action
