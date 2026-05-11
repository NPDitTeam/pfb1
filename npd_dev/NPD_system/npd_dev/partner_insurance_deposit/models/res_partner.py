# -*- coding: utf-8 -*-
# models/res_partner.py
# ไฟล์นี้ทำหน้าที่เพิ่มฟิลด์ใหม่ให้กับ model res.partner
# โดยใช้วิธี _inherit เพื่อสืบทอดและขยายความสามารถของ model เดิม

from odoo import models, fields, api


class ResPartnerInherit(models.Model):
    """
    Class นี้ inherit จาก res.partner เพื่อเพิ่มฟิลด์ค่าประกันสะสม

    การใช้ _inherit = 'res.partner' หมายความว่า:
    - ไม่ได้สร้าง model ใหม่ แต่เป็นการขยาย model res.partner ที่มีอยู่แล้ว
    - ฟิลด์ใหม่จะถูกเพิ่มเข้าไปใน table res_partner ในฐานข้อมูล
    - สามารถใช้ฟิลด์นี้ร่วมกับฟิลด์เดิมทั้งหมดของ res.partner ได้
    """

    _inherit = 'res.partner'  # ระบุว่าจะ inherit จาก model ไหน

    # ฟิลด์ค่าประกันสะสม (Accumulated Insurance Deposit)
    # ใช้ Monetary เพื่อแสดงเป็นสกุลเงิน
    # compute: ระบุชื่อ method ที่จะใช้คำนวณค่า
    # store=False: คำนวณใหม่ทุกครั้งที่เปิดหน้า (real-time)
    accumulated_insurance_deposit = fields.Monetary(
        string='ค่าประกันสะสม',  # label ที่แสดงในหน้าจอ
        compute='_compute_accumulated_insurance_deposit',  # method ที่ใช้คำนวณ
        store=False,  # ไม่เก็บค่าลงฐานข้อมูล - คำนวณใหม่ทุกครั้ง
        currency_field='currency_id',  # ฟิลด์สกุลเงิน
        help='ค่าประกันสะสม = ยอดรับชำระค่าประกัน - ยอดคืนเงินประกัน',
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

        สูตรการคำนวณ:
        ค่าประกันสะสม = ยอดรับชำระค่าประกัน (account.payment)
                      - ยอดคืนเงินประกัน (account.voucher)

        หลักการทำงาน:
        1. คำนวณยอดรับ: ค้นหา account.payment ที่
           - partner_id = ลูกค้ารายนี้
           - journal_id = "สมุดรายวันรับชำระค่าประกัน"
           - state = 'posted'

        2. คำนวณยอดคืน: ค้นหา account.voucher.line ที่
           - voucher_id.partner_id = ลูกค้ารายนี้
           - voucher_id.state = 'posted'
           - product_id.name = "เงินประกันค่าเช่า"

        3. ค่าประกันสะสม = ยอดรับ - ยอดคืน
        """
        # ====== ส่วนที่ 1: ค้นหา Journal สำหรับรับชำระค่าประกัน ======
        insurance_journal = self.env['account.journal'].search([
            ('name', '=', 'สมุดรายวันรับชำระค่าประกัน')
        ], limit=1)

        # ====== ส่วนที่ 2: ค้นหา Product สำหรับคืนเงินประกัน ======
        # ค้นหา product ที่ชื่อ "เงินประกันค่าเช่า"
        insurance_product = self.env['product.product'].search([
            ('name', '=', 'เงินประกันค่าเช่า')
        ], limit=1)

        for partner in self:
            total_received = 0.0  # ยอดรับชำระค่าประกัน
            total_refunded = 0.0  # ยอดคืนเงินประกัน

            # ====== ส่วนที่ 3: คำนวณยอดรับชำระค่าประกัน ======
            if insurance_journal:
                # ค้นหา payment ที่ตรงตามเงื่อนไข
                payments = self.env['account.payment'].search([
                    ('partner_id', 'in', [partner.id, partner.commercial_partner_id.id]),
                    ('journal_id', '=', insurance_journal.id),
                    ('state', '=', 'posted'),
                ])
                # รวมยอดเงินจาก payment ทั้งหมด
                total_received = sum(payments.mapped('amount'))

            # ====== ส่วนที่ 4: คำนวณยอดคืนเงินประกัน ======
            if insurance_product:
                # ค้นหา voucher line ที่:
                # - voucher.partner_id = ลูกค้ารายนี้
                # - voucher.state = 'posted'
                # - product_id = เงินประกันค่าเช่า
                voucher_lines = self.env['account.voucher.line'].search([
                    ('voucher_id.partner_id', 'in', [partner.id, partner.commercial_partner_id.id]),
                    ('voucher_id.state', '=', 'posted'),
                    ('product_id', '=', insurance_product.id),
                ])
                # รวมยอด price_unit จาก voucher line ทั้งหมด
                total_refunded = sum(voucher_lines.mapped('price_unit'))

            # ====== ส่วนที่ 5: คำนวณค่าประกันสะสม ======
            # ค่าประกันสะสม = ยอดรับ - ยอดคืน
            partner.accumulated_insurance_deposit = total_received - total_refunded

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


