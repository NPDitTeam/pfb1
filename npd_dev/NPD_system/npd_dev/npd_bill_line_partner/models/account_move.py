# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

BILL_TYPES = ('in_invoice', 'in_refund', 'in_receipt')


class AccountMove(models.Model):
    _inherit = 'account.move'

    npd_require_line_partner = fields.Boolean(
        compute='_compute_npd_require_line_partner',
        string='บังคับระบุ Partner รายบรรทัด')

    @api.depends('partner_id', 'partner_id.name', 'partner_id.npd_require_line_partner', 'move_type')
    def _compute_npd_require_line_partner(self):
        for move in self:
            move.npd_require_line_partner = bool(
                move.move_type in BILL_TYPES and move.partner_id and move.partner_id._npd_needs_line_partner())

    def _npd_check_line_partner(self):
        for move in self.filtered('npd_require_line_partner'):
            number = move.name if move.name and move.name != '/' else ''
            lines = move.invoice_line_ids.filtered(lambda l: not l.display_type and not l.npd_line_partner_id)
            if lines:
                raise UserError(_(
                    'บิล %s ของ %s ต้องระบุ Partner ทุกบรรทัดในแท็บ รายการจากใบแจ้งหนี้\nบรรทัดที่ยังไม่ระบุ:\n%s'
                ) % (number, move.partner_id.display_name,
                     '\n'.join('- %s' % (l.name or l.product_id.display_name or '') for l in lines)))
            if 'tax_invoice_ids' not in move._fields:
                continue
            vendor = move.partner_id.commercial_partner_id
            line_partners = move.invoice_line_ids.mapped('npd_line_partner_id.commercial_partner_id')
            # ใบกำกับภาษียังเป็นชื่อผู้ขาย (ธนาคาร) ได้เฉพาะเมื่อมีบรรทัดที่เป็นของผู้ขายเองจริง (เช่น ค่าธรรมเนียม)
            bad = move.tax_invoice_ids.filtered(
                lambda t: not t.partner_id
                or (t.partner_id.commercial_partner_id == vendor and vendor not in line_partners))
            if bad:
                raise UserError(_(
                    'บิล %s ของ %s ต้องระบุ Partner (ผู้ออกใบกำกับภาษีจริง) ทุกบรรทัดในแท็บ Tax Invoice\n'
                    'ตอนนี้ยังว่างหรือยังเป็นชื่อ %s: %s'
                ) % (number, move.partner_id.display_name, vendor.display_name,
                     ', '.join(t.tax_invoice_number or '(ไม่มีเลข)' for t in bad)))

    def _npd_fill_tax_invoice_partner(self):
        """ใบกำกับภาษีที่ยังว่างหรือเป็นชื่อผู้ขาย (ธนาคาร) ใส่ Partner ให้ ถ้าทุกบรรทัดระบุ Partner เป็นรายเดียวกัน"""
        for move in self.filtered('npd_require_line_partner'):
            if 'tax_invoice_ids' not in move._fields:
                continue
            partners = move.invoice_line_ids.filtered(lambda l: not l.display_type).mapped('npd_line_partner_id')
            if len(partners) != 1:
                continue
            vendor = move.partner_id.commercial_partner_id
            move.tax_invoice_ids.filtered(
                lambda t: not t.partner_id or t.partner_id.commercial_partner_id == vendor
            ).write({'partner_id': partners.id})

    def action_post(self):
        self._npd_fill_tax_invoice_partner()
        self._npd_check_line_partner()
        return super().action_post()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    npd_line_partner_id = fields.Many2one(
        'res.partner', string='Partner', index=True,
        help='ผู้ขาย/ผู้ออกใบกำกับภาษีที่แท้จริงของบรรทัดนี้ (เช่น ปั๊มน้ำมันในบิลบัตรเติมน้ำมัน) '
             'ช่องแยกจากผู้ขายของบิล ไม่กระทบเจ้าหนี้')
