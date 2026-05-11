# -*- coding: utf-8 -*-
from odoo import models, fields, api
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class TaxReceivableWizard(models.TransientModel):
    _name = 'tax.receivable.wizard'
    _description = 'Wizard สำหรับรายงานลูกหนี้ค้าง Tax'

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

    def action_generate_report(self):
        """สร้างรายงานลูกหนี้ค้าง Tax"""
        _logger.warning("=" * 80)
        _logger.warning("🔍 START: Tax Receivable Report")
        _logger.warning("=" * 80)

        # Log เงื่อนไขที่เลือก
        _logger.warning(f"📅 date_from: {self.date_from}")
        _logger.warning(f"📅 date_to: {self.date_to}")
        _logger.warning(f"🏢 branch_ids: {self.branch_ids.mapped('name')}")
        
        # ลบข้อมูลเก่าทั้งหมด
        self.env['tax.receivable.report'].sudo().search([]).unlink()

        # สร้าง domain สำหรับค้นหา account.payment
        payment_domain = [
            ('state', '=', 'posted'),
            ('wht_has_slip', '=', True),
        ]

        # เพิ่มเงื่อนไขวันที่ถ้ามี
        if self.date_from:
            payment_domain.append(('date', '>=', self.date_from))
        if self.date_to:
            payment_domain.append(('date', '<=', self.date_to))

        # กรองตามสาขาถ้าเลือก
        if self.branch_ids:
            payment_domain.append(('branch_id', 'in', self.branch_ids.ids))

        _logger.warning(f"🔎 Payment Domain: {payment_domain}")

        # ค้นหา Payments
        payments = self.env['account.payment'].sudo().search(payment_domain)
        _logger.warning(f"📋 Found Payments: {len(payments)} records")
        
        for p in payments:
            _logger.warning(f"   💳 Payment: {p.name} | Partner: {p.partner_id.name} | Date: {p.date} | Branch: {p.branch_id.name if p.branch_id else 'N/A'} | wht_has_slip: {p.wht_has_slip}")

        if not payments:
            _logger.warning("❌ No payments found!")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'ไม่พบข้อมูล',
                    'message': 'ไม่พบข้อมูลหัก ณ ที่จ่ายตามเงื่อนไขที่เลือก',
                    'type': 'warning',
                }
            }

        # ดึงยอดหัก ณ ที่จ่าย จาก account.paid.line แยกตามลูกค้า
        withholding_data = defaultdict(float)
        
        _logger.warning("=" * 40)
        _logger.warning("🔍 Checking paid_ids for each payment:")
        
        for payment in payments:
            partner_id = payment.partner_id.id if payment.partner_id else False
            _logger.warning(f"   💳 Payment: {payment.name} | Partner ID: {partner_id}")
            _logger.warning(f"      📦 paid_ids count: {len(payment.paid_ids)}")
            
            if not partner_id:
                _logger.warning(f"      ⚠️ SKIP: No partner_id")
                continue
            
            # ใช้ paid_ids (One2many ไปยัง account.paid.line)
            for line in payment.paid_ids:
                method_name = line.payment_method_id.name if line.payment_method_id else 'N/A'
                _logger.warning(f"      📝 Line: method={method_name} | total={line.total}")
                _logger.warning(f"      🔍 method_name repr: {repr(method_name)}")
                
                if line.payment_method_id and line.payment_method_id.name:
                    # ใช้ strip() และเปรียบเทียบแบบ contains
                    method_clean = method_name.strip() if method_name else ''
                    search_text = 'ภาษีเงินได้ถูกหัก ณ ที่จ่าย'
                    
                    # ลองหลายวิธีเปรียบเทียบ
                    is_match = (
                        search_text in method_clean or 
                        'ภาษีเงินได้' in method_clean or
                        'หัก ณ ที่จ่าย' in method_clean or
                        method_clean == search_text
                    )
                    
                    _logger.warning(f"      🔍 method_clean: '{method_clean}'")
                    _logger.warning(f"      🔍 is_match: {is_match}")
                    
                    if is_match:
                        withholding_data[partner_id] += line.total or 0.0
                        _logger.warning(f"      ✅ MATCHED! Added {line.total} to partner {partner_id}")
                    else:
                        _logger.warning(f"      ❌ NOT MATCHED")

        _logger.warning("=" * 40)
        _logger.warning(f"📊 withholding_data: {dict(withholding_data)}")

        if not withholding_data:
            _logger.warning("❌ No withholding data found!")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'ไม่พบข้อมูล',
                    'message': 'ไม่พบข้อมูลหัก ณ ที่จ่ายตามเงื่อนไขที่เลือก',
                    'type': 'warning',
                }
            }

        # ดึง partner_ids จากข้อมูลหัก ณ ที่จ่าย
        partner_ids = list(withholding_data.keys())
        _logger.warning(f"👥 Partner IDs with WHT: {partner_ids}")

        # ดึงข้อมูลลูกค้า
        partners = self.env['res.partner'].sudo().browse(partner_ids)

        # เตรียมข้อมูลที่จะสร้าง
        records_to_create = []
        
        for partner in partners:
            wht_amount = withholding_data.get(partner.id, 0.0)
            _logger.warning(f"   👤 Partner: {partner.name} | WHT Amount: {wht_amount}")
            
            # ข้ามถ้าไม่มียอดหัก ณ ที่จ่าย
            if wht_amount <= 0:
                _logger.warning(f"      ⚠️ SKIP: wht_amount <= 0")
                continue
            
            # สร้างที่อยู่ลูกค้า
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
            
            records_to_create.append({
                'partner_id': partner.id,
                'partner_code': partner.ref or str(partner.id),
                'partner_name': partner.name or '-',
                'partner_phone': partner.phone or partner.mobile or '-',
                'partner_address': ', '.join(filter(None, address_parts)) or '-',
                'withholding_tax_amount': wht_amount,
            })
            _logger.warning(f"      ✅ Added to records_to_create")

        _logger.warning("=" * 40)
        _logger.warning(f"📋 Total records_to_create: {len(records_to_create)}")

        # สร้างข้อมูลทั้งหมด
        if records_to_create:
            self.env['tax.receivable.report'].sudo().create(records_to_create)
            _logger.warning("✅ Records created successfully!")

        _logger.warning("=" * 80)
        _logger.warning("🔍 END: Tax Receivable Report")
        _logger.warning("=" * 80)

        # เปิดหน้า Tree View แสดงผลลัพธ์
        action = {
            'type': 'ir.actions.act_window',
            'name': f'รายงานลูกหนี้ค้าง Tax - พบ {len(records_to_create)} ราย',
            'res_model': 'tax.receivable.report',
            'view_mode': 'tree',
            'target': 'current',
        }

        try:
            tree_view = self.env.ref('all_receivable_report.view_tree_tax_receivable_report', False)
            if tree_view:
                action['views'] = [(tree_view.id, 'tree')]
        except:
            pass

        return action
