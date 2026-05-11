# -*- coding: utf-8 -*-
"""
VAT Calculate From Total - Purchase Order Override

คำนวณ VAT จากยอดรวมสินค้าแทนการคำนวณทีละบรรทัด
รองรับทั้ง Tax Excluded และ Tax Included

ตัวอย่าง Tax Excluded (ภาษีขายรวม VAT 7%):
    Line 1: 100.33 บาท
    Line 2: 200.33 บาท
    Line 3: 150.33 บาท
    ─────────────────────────────
    แบบเดิม (per line):
        VAT = round(100.33*0.07) + round(200.33*0.07) + round(150.33*0.07)
            = 7.02 + 14.02 + 10.52 = 31.56
    แบบใหม่ (from total):
        VAT = round((100.33 + 200.33 + 150.33) * 0.07)
            = round(450.99 * 0.07) = round(31.5693) = 31.57

ตัวอย่าง Tax Included (ภาษีขายไม่รวม VAT 7%):
    Line 1: 107.00 บาท (รวม VAT)
    Line 2: 214.00 บาท (รวม VAT)
    ─────────────────────────────
    แบบใหม่ (from total):
        Total Included = 107.00 + 214.00 = 321.00
        Untaxed = round(321.00 / 1.07) = round(300.00) = 300.00
        VAT = 321.00 - 300.00 = 21.00
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    vat_calculation_method = fields.Selection([
        ('from_total', 'คำนวณจากยอดรวม (From Total)'),
        ('per_line', 'คำนวณทีละบรรทัด (Per Line)'),
    ], string='วิธีคำนวณ VAT', default='from_total',
       help='From Total: ถอด VAT จากยอดรวมทั้งหมดครั้งเดียว\n'
            'Per Line: ถอด VAT ทีละบรรทัดแล้วรวม (ปัดเศษแต่ละบรรทัด)')

    @api.depends('order_line.price_total', 'vat_calculation_method')
    def _amount_all(self):
        """
        Override: คำนวณ VAT จากยอดรวมแทนทีละบรรทัด

        Logic:
        1. เรียก super() เพื่อให้ line-level compute ทำงานปกติ
           (price_subtotal, price_tax, price_total ของแต่ละ line ยังคงเดิม)
        2. จัดกลุ่ม tax ตาม tax_id + price_include
        3. คำนวณ tax ใหม่จากยอดรวม
        4. อัปเดต amount_tax, amount_total ของ order
        """
        super(PurchaseOrder, self)._amount_all()

        for order in self:
            if not order.order_line:
                continue

            currency = (
                order.currency_id
                or order.partner_id.property_purchase_currency_id
                or self.env.company.currency_id
            )

            # จัดกลุ่ม lines ตาม tax
            tax_groups = self._group_lines_by_tax(order.order_line)

            if not tax_groups:
                continue

            # คำนวณ tax ใหม่จากยอดรวม
            new_amount_tax = 0.0
            new_amount_untaxed = 0.0

            for tax_key, group_data in tax_groups.items():
                tax = group_data['tax']
                lines = group_data['lines']

                if tax.amount_type != 'percent':
                    # สำหรับ tax ที่ไม่ใช่ percent (fixed, division, etc.)
                    # ใช้ค่าเดิมจาก per-line calculation
                    new_amount_tax += sum(l.price_tax for l in lines)
                    new_amount_untaxed += sum(l.price_subtotal for l in lines)
                    continue

                method = order.vat_calculation_method or 'from_total'

                if tax.price_include:
                    rate = tax.amount  # เช่น 7.0

                    if method == 'per_line':
                        # === Per Line: ถอด VAT ทีละบรรทัดแล้วรวม ===
                        group_tax = 0.0
                        group_untaxed = 0.0
                        for line in lines:
                            line_incl = currency.round(
                                line.price_unit * line.product_qty)
                            line_tax = currency.round(
                                line_incl * rate / (100.0 + rate))
                            group_tax += line_tax
                            group_untaxed += (line_incl - line_tax)
                        new_amount_untaxed += currency.round(group_untaxed)
                        new_amount_tax += currency.round(group_tax)
                    else:
                        # === From Total: ถอด VAT จากยอดรวมครั้งเดียว ===
                        total_incl = 0.0
                        for line in lines:
                            total_incl += currency.round(
                                line.price_unit * line.product_qty)
                        group_tax = currency.round(
                            total_incl * rate / (100.0 + rate))
                        group_untaxed = total_incl - group_tax
                        new_amount_untaxed += currency.round(group_untaxed)
                        new_amount_tax += currency.round(group_tax)
                else:
                    if method == 'per_line':
                        # === Per Line: คำนวณ tax ทีละบรรทัด ===
                        group_tax = 0.0
                        group_untaxed = 0.0
                        for line in lines:
                            line_untaxed = line.price_subtotal
                            line_tax = currency.round(
                                line_untaxed * tax.amount / 100.0)
                            group_tax += line_tax
                            group_untaxed += line_untaxed
                        new_amount_untaxed += currency.round(group_untaxed)
                        new_amount_tax += currency.round(group_tax)
                    else:
                        # === From Total: คำนวณ tax จากยอดรวม ===
                        total_untaxed = sum(
                            l.price_subtotal for l in lines)
                        tax_amount = currency.round(
                            total_untaxed * tax.amount / 100.0)
                        new_amount_untaxed += total_untaxed
                        new_amount_tax += tax_amount

            # รวม lines ที่ไม่มี tax
            lines_no_tax = order.order_line.filtered(
                lambda l: not l.taxes_id
                and l.display_type not in ('line_section', 'line_note')
            )
            new_amount_untaxed += sum(l.price_subtotal for l in lines_no_tax)

            # อัปเดตยอดรวมของ order
            order.update({
                'amount_untaxed': currency.round(new_amount_untaxed),
                'amount_tax': currency.round(new_amount_tax),
                'amount_total': currency.round(new_amount_untaxed + new_amount_tax),
            })

            _logger.debug(
                'VAT From Total [PO %s]: untaxed=%.2f, tax=%.2f, total=%.2f',
                order.name, new_amount_untaxed, new_amount_tax,
                new_amount_untaxed + new_amount_tax
            )

    @api.model
    def _group_lines_by_tax(self, lines):
        """
        จัดกลุ่ม order lines ตาม tax_id

        รองรับกรณี:
        - line มี tax เดียว → จัดกลุ่มตาม tax_id
        - line มีหลาย tax → แยก compute ตาม tax แต่ละตัว
        - line ไม่มี tax → ข้าม (จะรวมทีหลัง)

        Returns:
            dict: {tax_id: {'tax': account.tax record, 'lines': recordset}}
        """
        tax_groups = {}

        for line in lines:
            # ข้าม section/note lines
            if line.display_type in ('line_section', 'line_note'):
                continue

            if not line.taxes_id:
                continue

            for tax in line.taxes_id:
                if tax.id not in tax_groups:
                    tax_groups[tax.id] = {
                        'tax': tax,
                        'lines': self.env['purchase.order.line'],
                    }
                tax_groups[tax.id]['lines'] |= line

        return tax_groups
