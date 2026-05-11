# -*- coding: utf-8 -*-
import logging
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)
class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.depends('order_line.price_total')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = amount_discount = price_tax = 0.0
            for line in order.order_line:
                line._compute_amount()
                if line.discount_unit > 0:
                    amount_discount += line.discount_unit

                    for tax in line.taxes_id:
                        if tax.price_include == False:
                            price_tax = (line.price_subtotal * tax.amount) / 100
                            print('1. price_unit---------->', line.price_subtotal)
                            print('2. discount_unit---------->', line.discount_unit)
                            print('3. price_tax---------->', price_tax)

                if line.discount > 0:
                    amount_discount += (line.price_unit * line.product_qty) - line.price_subtotal
                amount_untaxed += line.price_subtotal

                if price_tax > 0:
                    amount_tax += price_tax
                else:
                    amount_tax += line.price_tax
            order.update({
                'amount_untaxed': order.currency_id.round(amount_untaxed),
                'amount_tax': order.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
                'amount_discount': amount_discount,
            })

    amount_discount = fields.Monetary(string='Discount', store=True, readonly=True, compute='_amount_all',  track_visibility='always')


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    discount_unit = fields.Float(string="Discount")

    @api.depends("discount","discount_unit")
    def _compute_amount(self):
        return super()._compute_amount()

    @api.depends('product_qty', 'price_unit', 'taxes_id',"discount","discount_unit")
    def _compute_amount(self):
        res = super()._compute_amount()
        for line in self:
            if line.discount_unit:
                print('self.price_subtotal',line.price_subtotal)
                line.update({
                    'price_subtotal': line.price_subtotal - (line.discount_unit or 0.0),
                })
        return res

    # def _prepare_compute_all_values(self):
    #     vals = super()._prepare_compute_all_values()
    #     vals.update({"price_unit": self._get_discounted_price_unit()})
    #     return vals
    #
    # def _get_discounted_price_unit(self):
    #     """Inheritable method for getting the unit price after applying
    #     discount(s).
    #
    #     :rtype: float
    #     :return: Unit price after discount(s).
    #     """
    #     if self.discount_unit:
    #         self.ensure_one()
    #         print('price_unit >> product_qty',self.price_unit * self.product_qty)
    #         print('price_unit', self.price_unit)
    #         print('discount_unit', self.price_unit * self.product_qty - (self.discount_unit or 0.0))
    #         return (self.price_unit * self.product_qty) - (self.discount_unit or 0.0)
    #     else:
    #         return super()._get_discounted_price_unit()

