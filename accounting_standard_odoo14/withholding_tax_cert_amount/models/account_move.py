# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends('invoice_line_ids.wt_tax_id','invoice_line_ids.price_subtotal')
    def _get_wht_amount(self):
        for move in self:
            amount_wt = base_amount = 0
            inv_lines = move.mapped("invoice_line_ids").filtered("wt_tax_id")
            for line in inv_lines:
                base_amount = line._get_wt_base_amount()
                amount_wt = amount_wt + line.wt_tax_id.amount / 100 * base_amount
            move.wht_amt_net = move.amount_total - amount_wt
            move.update({'wht_amt': amount_wt, 'wht_base': base_amount})

    wht_amt = fields.Float(string='WHT Amount', compute='_get_wht_amount', store=True)
    wht_base = fields.Float(string='WHT Base', compute='_get_wht_amount', store=True)
    wht_amt_net = fields.Float(string='Net Amount', compute='_get_wht_amount', store=True)