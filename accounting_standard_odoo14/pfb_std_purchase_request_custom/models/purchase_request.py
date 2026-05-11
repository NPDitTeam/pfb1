# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import pytz
import logging

logger = logging.getLogger(__name__)
import time
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Pfbuse_pr(models.Model):
    _inherit = "purchase.request"

    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    amount_untaxed = fields.Monetary('Untaxed Amount', compute='_compute_amount_total', store=True)
    amount_tax = fields.Monetary('Taxes', compute='_compute_amount_total', store=True)
    amount_total = fields.Monetary(string="Total", compute="_compute_amount_total", readonly=True, store="true",)

    @api.depends('line_ids.product_qty', 'line_ids.estimated_cost')
    def _compute_amount_total(self):
        for pr in self:
            amount_untaxed = amount_tax = 0.0
            for line in pr.line_ids:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            pr.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })



class Pfbuse_pr_line(models.Model):
    _inherit = "purchase.request.line"

    def _get_default_tax_id(self):
        if self.env.company.account_purchase_tax_id:
            return self.env.company.account_purchase_tax_id

    tax_id = fields.Many2one('account.tax', string='Tax', domain="[('type_tax_use', '=', 'purchase')]")
    price_tax = fields.Float(compute='_compute_amount', string='Total Tax', readonly=True, store=True)
    suggest_vendor = fields.Char(string="Suggest Vendor")
    price_subtotal = fields.Monetary(compute='_compute_amount', string="Subtotal", readonly=True)
    cancelled = fields.Boolean(string="Cancelled")

    @api.depends('product_qty', 'estimated_cost', 'tax_id')
    def _compute_amount(self):
        for line in self:
            price = line.estimated_cost
            taxes = line.tax_id.compute_all(price, line.request_id.currency_id, line.product_qty,
                                            product=line.product_id, partner=line.request_id.requested_by)
            print('taxes')
            print(price)
            print(line.request_id.currency_id)
            print(line.product_qty)
            print(line.product_id)
            print(line.request_id.requested_by)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                # 'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded']
            })

    @api.onchange("cancelled")
    def _onchange_cancelled(self):
        if self.cancelled:
            self.purchase_state = 'cancel'
        for line in self:
            line.price_subtotal = line.product_qty * line.estimated_cost

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(Pfbuse_pr_line, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        pr_lines = self.env['purchase.request.line'].search([('cancelled', '=', True)], limit=5000)
        for each in pr_lines:
            each.purchase_state = 'cancel'
        return res



            # add news colum on list view

    rfq_numbers = fields.Char(
        string="RFQ numbers", compute="_compute_rfq_numbers", readonly=True
    )
    po_numbers = fields.Char(
        string="PO numbers", compute="_compute_po_numbers", readonly=True
    )
    product_categ = fields.Char(string="Product Category", compute="_compute_product_categs", readonly=True)

    @api.depends("purchase_lines")
    def _compute_rfq_numbers(self):
        for rec in self:
            str1 = ""
            for ele in rec.mapped("purchase_lines.order_id.name"):
                if str1 != "":
                    str1 += "," + ele
                else:
                    str1 += ele
            rec.rfq_numbers = str1

    @api.depends("product_id")
    def _compute_product_categs(self):
        for rec in self:
            str1 = ""
            for ele in rec.mapped("product_id.categ_id.name"):
                if ele:
                    if str1 != "":
                        str1 += "," + ele
                    else:
                        str1 += ele
            rec.product_categ = str1

    @api.depends("purchase_lines")
    def _compute_po_numbers(self):
        for rec in self:
            str1 = ""
            for ele in rec.mapped("purchase_lines.order_id.purchase_order_id.name"):
                if str1 != "":
                    str1 += "," + ele
                else:
                    str1 += ele
            rec.po_numbers = str1

    @api.depends("purchase_lines.state", "purchase_lines.order_id.state")
    def _compute_purchase_state(self):
        for rec in self:
            temp_purchase_state = False
            if rec.purchase_lines:
                user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
                elapse_start = datetime.today()
                try:
                    today = elapse_start.astimezone(user_tz)
                except:
                    today = user_tz.localize(elapse_start)
                if any(po_line.state == "done" for po_line in rec.purchase_lines):
                    temp_purchase_state = "done"
                elif all(po_line.state == "cancel" for po_line in rec.purchase_lines):
                    temp_purchase_state = "cancel"
                elif any(po_line.state == "purchase" for po_line in rec.purchase_lines):
                    temp_purchase_state = "purchase"
                elif any(
                        po_line.state == "to approve" for po_line in rec.purchase_lines
                ):
                    temp_purchase_state = "to approve"
                elif any(po_line.state == "sent" for po_line in rec.purchase_lines):
                    temp_purchase_state = "sent"
                elif all(
                        po_line.state in ("draft", "cancel")
                        for po_line in rec.purchase_lines
                ):
                    temp_purchase_state = "draft"
            rec.purchase_state = temp_purchase_state


class PurchaseRequestLineMakePurchaseOrder(models.TransientModel):
    _inherit = "purchase.request.line.make.purchase.order"

    def make_purchase_order(self):
        res = super().make_purchase_order()
        for data in self:
            domain = res.get('domain') or ''
            for po in self.env['purchase.order'].search(domain):
                po_line = po.env['purchase.order.line'].search([('order_id', '=', po.id)], limit=1)
                pr = po.env['purchase.request'].search([('id', '=', po_line.purchase_request_lines.request_id.id)],
                                                       limit=1)
                for line in po.order_line:
                    line.write({
                        'price_unit': line.purchase_request_lines.estimated_cost,
                    })
        return res


class Pfbuse_pr_item(models.TransientModel):
    _inherit = "purchase.request.line.make.purchase.order.item"
    analytic_account_id = fields.Many2one(comodel_name="account.analytic.account", string="Project")
    date_required = fields.Date(string="Request Date", related="line_id.date_required")
    suggest_vendor = fields.Char(string="Suggest Vendor", related="line_id.suggest_vendor")
    currency_id = fields.Many2one(related="line_id.company_id.currency_id", readonly=True, invisible=True)
    estimated_cost = fields.Monetary(string="estimated_cost", currency_field="currency_id",
                                     related="line_id.estimated_cost", invisible=True)
