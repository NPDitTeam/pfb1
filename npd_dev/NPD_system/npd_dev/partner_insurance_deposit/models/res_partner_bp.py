# -*- coding: utf-8 -*-
# models/res_partner.py
# ไฟล์นี้ทำหน้าที่เพิ่มฟิลด์ใหม่ให้กับ model res.partner
# โดยใช้วิธี _inherit เพื่อสืบทอดและขยายความสามารถของ model เดิม

from odoo import models, fields, api


class ResPartnerInherit(models.Model):
    """
    Class นี้ inherit จาก res.partner เพื่อเพิ่มฟิลด์:
    1. ค่าประกันสะสม - คำนวณจาก account.payment
    2. ประเภทลูกค้า - ดึงมาจาก crm.lead
    """
    
    _inherit = 'res.partner'  # ระบุว่าจะ inherit จาก model ไหน
    
    # ===== ฟิลด์ค่าประกันสะสม (Accumulated Insurance Deposit) =====
    # ใช้ Monetary เพื่อแสดงเป็นสกุลเงิน
    # compute: ระบุชื่อ method ที่จะใช้คำนวณค่า
    # store=False: คำนวณใหม่ทุกครั้งที่เปิดหน้า (real-time)
    accumulated_insurance_deposit = fields.Monetary(
        string='ค่าประกันสะสม',
        compute='_compute_accumulated_insurance_deposit',
        store=False,
        currency_field='currency_id',
        help='จำนวนเงินค่าประกันสะสมของคู่ค้ารายนี้ (คำนวณจากใบรับชำระที่ posted)',
    )
    
    # ===== ฟิลด์ประเภทลูกค้า (Customer Status) =====
    # ดึงมาจาก crm.lead field customer_status
    # เป็น Selection field: old = ลูกค้าเก่า, new = ลูกค้าใหม่
    customer_status = fields.Selection(
        selection=[
            ('old', 'ลูกค้าเก่า'),
            ('new', 'ลูกค้าใหม่'),
        ],
        string='ประเภทลูกค้า',
        compute='_compute_customer_status',
        store=False,
        help='ประเภทลูกค้า ดึงจาก CRM Lead ล่าสุด',
    )

    def _compute_accumulated_insurance_deposit(self):
        """
        Method สำหรับคำนวณยอดค่าประกันสะสม
        
        หลักการทำงาน:
        1. ค้นหา journal ที่ชื่อ "สมุดรายวันรับชำระค่าประกัน"
        2. ค้นหา account.payment ที่:
           - partner_id = ลูกค้ารายนี้
           - journal_id = สมุดรายวันรับชำระค่าประกัน
           - state = 'posted' (เฉพาะที่ผ่านการบันทึกแล้ว)
        3. รวมยอดเงิน (amount) ทั้งหมด
        """
        insurance_journal = self.env['account.journal'].search([
            ('name', '=', 'สมุดรายวันรับชำระค่าประกัน')
        ], limit=1)
        
        for partner in self:
            total_amount = 0.0
            
            if insurance_journal:
                payments = self.env['account.payment'].search([
                    ('partner_id', 'in', [partner.id, partner.commercial_partner_id.id]),
                    ('journal_id', '=', insurance_journal.id),
                    ('state', '=', 'posted'),
                ])
                total_amount = sum(payments.mapped('amount'))
            
            partner.accumulated_insurance_deposit = total_amount
    
    def _compute_customer_status(self):
        """
        Method สำหรับดึงประเภทลูกค้าจาก CRM Lead
        
        หลักการทำงาน:
        1. ค้นหา crm.lead ที่ partner_id = ลูกค้ารายนี้
        2. เรียงตามวันที่สร้างล่าสุด (create_date desc)
        3. ดึง customer_status จาก lead ล่าสุด
        """
        for partner in self:
            customer_status = False
            
            # ค้นหา lead ที่เกี่ยวข้องกับ partner นี้
            # เรียงตาม create_date จากล่าสุด
            lead = self.env['crm.lead'].search([
                ('partner_id', 'in', [partner.id, partner.commercial_partner_id.id]),
            ], order='create_date desc', limit=1)
            
            if lead and hasattr(lead, 'customer_status'):
                customer_status = lead.customer_status
            
            partner.customer_status = customer_status
