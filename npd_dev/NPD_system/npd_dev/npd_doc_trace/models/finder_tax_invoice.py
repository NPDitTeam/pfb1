# -*- coding: utf-8 -*-
"""ค้นหาด้วยเลขใบกำกับภาษี (Tax Invoice Number) ในช่องค้นหาของ ตรวจสอบเอกสารที่เชื่อมโยง (ผู้ใช้สั่ง 23 ต.ค. 2569)

ดัชนีเลขเอกสาร (npd.doc.finder.line) มีแต่เลขของเอกสาร เลขใบกำกับอยู่ในแท็บ Tax Invoice
→ พิมพ์เลขใบกำกับแล้วได้เอกสารที่ถือใบกำกับนั้น (บิล/ใบแจ้งหนี้/รับ-จ่ายเงิน/ใบสำคัญ/เคลียร์เงินทดรอง)
"""
from odoo import api, models
from odoo.osv import expression

TAX_INVOICE_MODEL = 'account.move.tax.invoice'
TAX_INVOICE_LINKS = ('move_id', 'payment_id', 'voucher_id', 'advance_clear_id')
MIN_TAX_INVOICE_SEARCH = 4


class NpdDocFinderLine(models.Model):
    _inherit = 'npd.doc.finder.line'

    @api.model
    def _npd_tax_invoice_domain(self, name):
        if TAX_INVOICE_MODEL not in self.env or len(name) < MIN_TAX_INVOICE_SEARCH:
            return []
        TaxInv = self.env[TAX_INVOICE_MODEL].sudo()
        rows = TaxInv.search([('tax_invoice_number', 'ilike', name)], limit=200)
        domains = []
        for fname in TAX_INVOICE_LINKS:
            field = TaxInv._fields.get(fname)
            if not field or field.type != 'many2one':
                continue
            ids = rows.mapped(fname).ids
            if ids:
                domains.append(['&', ('res_model', '=', field.comodel_name), ('res_id', 'in', ids)])
        return expression.OR(domains) if domains else []

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        ids = list(super()._name_search(name, args=args, operator=operator, limit=limit,
                                        name_get_uid=name_get_uid))
        name = (name or '').strip()
        if name and operator in ('ilike', 'like', '=', '=ilike') and (not limit or len(ids) < limit):
            tax_domain = self._npd_tax_invoice_domain(name)
            if tax_domain:
                more = self._search(expression.AND([list(args or []), tax_domain]),
                                    limit=limit, access_rights_uid=name_get_uid)
                ids += [i for i in more if i not in ids]
        return ids[:limit] if limit else ids
