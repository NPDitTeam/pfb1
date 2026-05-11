# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleAdvanceRentInv(models.TransientModel):
    _name = "sale.advance.rent.inv"
    _description = "Sales Advance Rent Invoice"

    advance_payment_method = fields.Selection([
        ('percentage', 'Down payment (percentage)'),
        ('fixed', 'Down payment (fixed amount)')
    ], string='Create Invoice', default='percentage', required=True, )
    amount = fields.Float('Down Payment Amount', )

    def create_invoices(self):
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        invoice = self.env['account.move']
        amount = 0
        name = _('รับเงินประกัน')


        sale_orders_line = sale_orders.mapped('order_line')

        # Fetch the product_id as a string and convert it to a product record
        product_id = self.env['ir.config_parameter'].sudo().get_param('sale.deposit_default_npd_id')
        product = self.env['product.product'].browse(int(product_id))
        tax = False
        if self.advance_payment_method == 'percentage':
            if product.taxes_id:
                tax = [(6, 0, product.taxes_id.ids)]
                if product.taxes_id.price_include:
                    amount = sale_orders.amount_total * self.amount / 100
                    name = _("รับเงินประกัน %s%%") % self.amount
                else:
                    amount = sale_orders.amount_untaxed * self.amount / 100
                    name = _("รับเงินประกัน %s%%") % self.amount
            else:
                amount = sale_orders.amount_total * self.amount / 100
                name = _("รับเงินประกัน %s%%") % self.amount
        else:
            amount = self.amount
            if product.taxes_id:
                tax = [(6, 0, product.taxes_id.ids)]

        if not product:
            raise UserError("Product not found with the given ID from configuration parameter")

        invoice_vals = {
            'ref': sale_orders.client_order_ref,
            'move_type': 'out_invoice',
            'invoice_origin': sale_orders.name,
            'invoice_user_id': sale_orders.user_id.id,
            'narration': sale_orders.note,
            'partner_id': sale_orders.partner_invoice_id.id,
            'fiscal_position_id': (sale_orders.fiscal_position_id or sale_orders.fiscal_position_id.get_fiscal_position(
                sale_orders.partner_id.id)).id,
            'partner_shipping_id': sale_orders.partner_shipping_id.id,
            'currency_id': sale_orders.pricelist_id.currency_id.id,
            'payment_reference': sale_orders.reference,
            'invoice_payment_term_id': sale_orders.payment_term_id.id,
            'partner_bank_id': sale_orders.company_id.partner_id.bank_ids[:1].id,
            'team_id': sale_orders.team_id.id,
            'campaign_id': sale_orders.campaign_id.id,
            'medium_id': sale_orders.medium_id.id,
            'source_id': sale_orders.source_id.id,
            'invoice_line_ids': [(0, 0, {
                'name': name,
                'price_unit': amount,
                'quantity': 1.0,
                'product_id': product.id,  # Use the product record's ID
                'product_uom_id': product.uom_po_id.id,
                'tax_ids': tax,
            })],
        }

        new_invoice = invoice.create(invoice_vals)
        sale_orders.sudo().write({'rent_check': [(4, new_invoice.id)]})

        if self._context.get('open_invoices', False):
            return sale_orders.action_view_rent()

        return {'type': 'ir.actions.act_window_close'}

