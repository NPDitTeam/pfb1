# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import odoo.addons.decimal_precision as dp
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_is_zero
from itertools import groupby
from odoo.exceptions import UserError, ValidationError

class account_voucher(models.Model):
    _inherit = 'account.voucher'
    
    discount_method = fields.Selection([('fix', 'Fixed'), ('per', 'Percentage')], 'Discount Method',default='fix')
    discount_amount = fields.Float('Discount Amount',default=0.0)
    discount_amt = fields.Monetary(compute='_amount_all',store=True,string='- Discount',readonly=True)
    #discount_amt = fields.Monetary(store=True,string='- Discount',readonly=True)
    discount_type = fields.Selection([('line', 'Order Line')],string='Discount Applies to',default='line')
    #discount_type = fields.Selection([('line', 'Order Line'), ('global', 'Global')],string='Discount Applies to',default='line')
    discount_amt_line = fields.Float(compute='_amount_all', string='- Line Discount', digits_compute=dp.get_precision('Line Discount'), store=True, readonly=True)
    #discount_amt_line = fields.Float(string='- Line Discount', digits_compute=dp.get_precision('Line Discount'), store=True, readonly=True)
    amount_price_subtotal_without_discount = fields.Float(string="Subtotal without Discount" , readonly=True)    
    #amount = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all')
    #tax_amount1 = fields.Monetary(string='Tax Amount1',readonly=True, store=True, compute='_amount_all')
    
    amount = fields.Monetary(string='Total', store=True, readonly=True, compute='_compute_total')
    tax_amount = fields.Monetary(readonly=True, store=True, compute='_compute_total')

    def _create_tax_move(self,move_id,move_line_id,tax_line_id,tax_base=0.00,tax_amount=0.00):
        TaxInvoice = self.env["account.move.tax.invoice"]
        sum_tax_amount = 0
        
        for line in self.line_ids:
            sum_tax_amount += line.price_tax
        taxinv = TaxInvoice.create(
                {
                    "move_id": move_id,
                    "move_line_id": move_line_id.id,
                    "voucher_id": self.id,
                    "partner_id": self.partner_id.id,
                    "tax_invoice_number": move_line_id.move_id.name,
                    "tax_invoice_date": fields.Date.today() or False,
                    "tax_base_amount": self.amount_price_subtotal_without_discount - self.discount_amt_line,
                    "balance": sum_tax_amount,
                    'tax_line_id': tax_line_id,
                }
        )


    def first_move_line_get(self, move_id, company_currency, current_currency):
        debit = credit = 0.0
        amount = abs(self.amount)
        if self.voucher_type == 'purchase':
            # credit = self._convert(self.amount - self.wht_amount)
            if self.amount < 0:
                debit = amount
            else:
                credit = amount
        elif self.voucher_type == 'sale':
            # debit = self._convert(self.amount - self.wht_amount)
            if self.amount < 0:
                credit = amount
            else:
                debit = amount

        # if debit < 0.0: debit = 0.0
        # if credit < 0.0: credit = 0.0
        sign = debit - credit < 0 and -1 or 1
        #set the first line of the voucher

        move_line = {
                'name': self.payment_method_id.name or '/',
                'debit': debit,
                'credit': credit,
                'account_id': self.payment_method_id.account_id.id,
                'move_id': move_id,
                'journal_id': self.journal_id.id,
                'partner_id': self.partner_id.commercial_partner_id.id,
                'currency_id': company_currency != current_currency and current_currency or False,
                'amount_currency': (sign * abs(self.amount)  # amount < 0 for refunds
                    if company_currency != current_currency else 0.0),
                'date': self.account_date,
                'date_maturity': self.date_due,
            }
        return move_line
    def vat_move_line_create(self, move_id, company_currency, current_currency):
        tax_vals = self._get_tax_vals()
        Currency = self.env['res.currency']
        company_cur = Currency.browse(company_currency)
        current_cur = Currency.browse(current_currency)
        for tax in tax_vals:
            temp = {
                'account_id': tax_vals[tax]['account_id'],
                'name': tax_vals[tax]['name'],
                'tax_line_id': tax,
                'move_id': move_id,
                'date': self.account_date,
                'partner_id': self.partner_id.id,
                'debit': self.voucher_type != 'sale' and tax_vals[tax]['amount'] or 0.0,
                'credit': self.voucher_type == 'sale' and tax_vals[tax]['amount'] or 0.0,
            }
            if company_currency != current_currency:
                ctx = {}
                sign = temp['credit'] and -1 or 1
                amount_currency = company_cur._convert(tax_vals[tax]['amount'], current_cur, self.company_id,
                                                       self.account_date or fields.Date.today(), round=True)
                if self.account_date:
                    ctx['date'] = self.account_date
                temp['currency_id'] = current_currency
                temp['amount_currency'] = sign * abs(amount_currency)
            
            move_line_id = self.env['account.move.line'].create(temp)
            self._create_tax_move(move_id, move_line_id, tax,tax_vals[tax]['base'],tax_vals[tax]['amount'])
            if tax_vals[tax]['price_tax'] > 0:
                move_line_id.update({'tax_repartition_line_id': tax_vals[tax]['tax_repartition_line_id'],'balance' : tax_vals[tax]['price_tax']})
            else:
                move_line_id.update({'tax_repartition_line_id': tax_vals[tax]['tax_repartition_line_id']})
    def _get_tax_vals(self):
        for voucher in self:
            tax_vals = {}
            res_config= self.env.company
            price_tax = 0
            for line in voucher.line_ids:
                #calculate
                if res_config.tax_discount_policy == 'untax':
                    if line.discount_type == 'line':
                        if line.discount_method == 'fix':
                            if line.price_unit and line.quantity:
                                if line.discount_amount:
                                    taxes_amount_include = 0.0
                                    taxes_amount_execlude = 0.0
                                    if line.tax_ids:
                                        for tax_ids in line.tax_ids:
                                            if tax_ids.price_include:
                                                #not calculate WTH -3 % on PO
                                                if tax_ids.amount > 0:
                                                    taxes_amount_include = tax_ids.amount
                                            else:
                                                #not calculate WTH -3 % on PO
                                                if tax_ids.amount > 0:
                                                    taxes_amount_execlude = tax_ids.amount
                                        stwd = 0.0
                                        stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))
                                        discount_percent = (line.discount_amount/(line.quantity * stwd))*100
                                        price_unit_discount = line.price_unit  * (1 - (discount_percent or 0.0) / 100.0)
                                        #line.price_tax = (line.price_subtotal * (taxes_amount_include/100)) + (line.price_subtotal * (taxes_amount_execlude/100))
                                        price_tax = price_tax + (line.price_subtotal * (taxes_amount_include/100)) + (line.price_subtotal * (taxes_amount_execlude/100))
                                    else:
                                        price_unit_discount  = line.price_unit
                        elif line.discount_method == 'per':
                            taxes_amount_include = 0.0
                            taxes_amount_execlude = 0.0
                            if line.tax_ids:
                                for tax_ids in line.tax_ids:
                                    if tax_ids.price_include:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_include = tax_ids.amount
                                        if line.discount_amount > 0 :
                                            line.discount_amt = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include)) * line.discount_amount/100                                            
                                    else:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_execlude = tax_ids.amount
                                        if line.discount_amount > 0 :
                                            line.discount_amt = (line.quantity*line.price_unit) * line.discount_amount/100                                            
                            stwd = 0.0
                            stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))
                            price_unit_discount = line.price_unit - ((line.price_unit)*line.discount_amount/100)
                        else:
                            taxes_amount_include = 0.0
                            taxes_amount_execlude = 0.0    
                            cur_obj = self.env['res.currency']                        
                            if line.tax_ids:
                                for tax_ids in line.tax_ids:
                                    if tax_ids.price_include:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_include = tax_ids.amount
                                    else:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_execlude = tax_ids.amount
                            price_unit_discount = line.price_unit
                            taxes_res = line.tax_ids.compute_all(line.price_unit,cur_obj, line.quantity, line.product_id)
                            price_tax = price_tax + sum(t.get('amount', 0.00000) for t in taxes_res.get('taxes', []))


                tax_info = line.tax_ids.compute_all(price_unit_discount, voucher.currency_id, line.quantity, line.product_id, voucher.partner_id)
                for t in tax_info.get('taxes', False):
                    tax_vals.setdefault(
                        t['id'], {"amount": 0.0, "base": 0.0, "account_id": "", "tax_repartition_line_id":""}
                    )
                    tax_vals[t['id']]["account_id"] = t['account_id']
                    tax_vals[t['id']]["name"] = t['name']
                    tax_vals[t['id']]["tax_repartition_line_id"] = t['tax_repartition_line_id']
                    tax_vals[t['id']]["amount"] += t["amount"]
                    tax_vals[t['id']]["base"] += t["base"]
                    tax_vals[t['id']]["price_tax"] = price_tax
            return tax_vals
                                
    @api.depends('tax_correction', 'line_ids.price_subtotal','wt_cert_ids')
    def _compute_total(self):
        tax_calculation_rounding_method = self.env.user.company_id.tax_calculation_rounding_method
        for voucher in self:
            total = 0
            tax_amount = 0
            tax_lines_vals_merged = {}

            for line in voucher.line_ids:
                tax_info = line.tax_ids.compute_all(line.price_unit, voucher.currency_id, line.quantity, line.product_id, voucher.partner_id)
                if tax_calculation_rounding_method == 'round_globally':
                    total += tax_info.get('total_excluded', 0.0)
                    for t in tax_info.get('taxes', False):
                        key = (
                            t['id'],
                            t['account_id'],
                        )
                        if key not in tax_lines_vals_merged:
                            tax_lines_vals_merged[key] = t.get('amount', 0.0)
                        else:
                            tax_lines_vals_merged[key] += t.get('amount', 0.0)
                else:
                    total += tax_info.get('total_included', 0.0)
                    tax_amount += sum([t.get('amount', 0.0) for t in tax_info.get('taxes', False)])
            if tax_calculation_rounding_method == 'round_globally':
                tax_amount = sum([voucher.currency_id.round(t) for t in tax_lines_vals_merged.values()])
                #voucher.amount = total + tax_amount + voucher.tax_correction
            #else:
                #voucher.amount = total + voucher.tax_correction
            #voucher.tax_amount = 11111
            voucher.wht_amount = sum(line.tax_amount for line in voucher.wt_cert_ids)


    @api.depends('tax_correction', 'line_ids.price_subtotal','wt_cert_ids','tax_correction','wt_cert_ids','line_ids','line_ids.price_subtotal',\
        'line_ids.quantity','discount_amount',\
        'discount_method','discount_type' ,'line_ids.discount_amount',\
        'line_ids.discount_method','line_ids.price_tax')
    def _amount_all(self):
        """
        Compute the total amounts of the voucher.
        """
        res_config= self.env.company
        cur_obj = self.env['res.currency']
        for order in self:
            applied_discount = line_discount = sums = order_discount =  amount_untaxed = amount_tax  = 0.0
            amount_price_subtotal_without_discount = 0.0
            for line in order.line_ids:
               #calculate
                if res_config.tax_discount_policy == 'untax':
                    if line.discount_type == 'line':
                        if line.discount_method == 'fix':
                            if line.price_unit and line.quantity:
                                if line.discount_amount:
                                    taxes_amount_include = 0.0
                                    taxes_amount_execlude = 0.0
                                    if line.tax_ids:
                                        for tax_ids in line.tax_ids:
                                            if tax_ids.price_include:
                                                #not calculate WTH -3 % on PO
                                                if tax_ids.amount > 0:
                                                    taxes_amount_include = tax_ids.amount
                                            else:
                                                #not calculate WTH -3 % on PO
                                                if tax_ids.amount > 0:
                                                    taxes_amount_execlude = tax_ids.amount


                                        stwd = 0.0
                                        stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))

                                        discount_percent = (line.discount_amount/(line.quantity * stwd))*100

                                        #discount_percent = (line.discount_amount/((line.quantity * line.price_unit)))*100
                                        price_unit_discount = line.price_unit  * (1 - (discount_percent or 0.0) / 100.0)
                                        taxes_res = line.tax_ids.compute_all(price_unit_discount,cur_obj, line.quantity, line.product_id)
                                        line.price_subtotal = stwd - line.discount_amount #taxes_res['total_excluded']
                                        #line.price_tax = sum(t.get('amount', 0.0) for t in taxes_res.get('taxes', []))
                                        line.price_tax = (line.price_subtotal * (taxes_amount_include/100)) + (line.price_subtotal * (taxes_amount_execlude/100))
                                        line.price_subtotal_without_discount =  stwd
                                    else:
                                        line.price_subtotal = (line.quantity*line.price_unit) - line.discount_amount
                                        line.price_subtotal_without_discount =  (line.quantity*line.price_unit)
                                        line.price_tax = 0                                        
                        elif line.discount_method == 'per':
                            cur_obj = self.env['res.currency']
                            taxes_amount_include = 0.0
                            taxes_amount_execlude = 0.0
                            if line.tax_ids:
                                for tax_ids in line.tax_ids:
                                    if tax_ids.price_include:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_include = tax_ids.amount
                                        if line.discount_amount > 0 :
                                            line.discount_amt = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include)) * line.discount_amount/100                                            
                                    else:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_execlude = tax_ids.amount
                                        if line.discount_amount > 0 :
                                            line.discount_amt = (line.quantity*line.price_unit) * line.discount_amount/100                                            
                            stwd = 0.0
                            stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))
                            price_unit_discount = line.price_unit - ((line.price_unit)*line.discount_amount/100)
                            taxes_res = line.tax_ids.compute_all(price_unit_discount,cur_obj, line.quantity, line.product_id)
                            line.price_subtotal = taxes_res['total_excluded']
                            line.price_tax = sum(t.get('amount', 0.00000) for t in taxes_res.get('taxes', []))
                            line.price_subtotal_without_discount =  (line.quantity*line.price_unit)
                            line.price_subtotal_without_discount =  stwd


                        else:
                            taxes_amount_include = 0.0
                            taxes_amount_execlude = 0.0                            
                            cur_obj = self.env['res.currency']
                            if line.tax_ids:
                                for tax_ids in line.tax_ids:
                                    if tax_ids.price_include:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_include = tax_ids.amount
                                    else:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_execlude = tax_ids.amount
                            taxes_res = line.tax_ids.compute_all(line.price_unit,cur_obj, line.quantity, line.product_id)
                            stwd = 0.0
                            stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))
                            line.price_subtotal_without_discount =  stwd
                            line.price_tax = sum(t.get('amount', 0.00000) for t in taxes_res.get('taxes', []))
                            
                
                #close calculate
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
                applied_discount += line.discount_amt
                amount_price_subtotal_without_discount += line.price_subtotal_without_discount #(line.quantity*line.price_unit)
                if line.discount_method == 'fix':
                    line_discount += line.discount_amount
                elif line.discount_method == 'per':
                    #tax = line.com_tax()
                    #line_discount += line.discount_amt #(line.price_subtotal + tax) * (line.discount_amount/ 100)
                    line_discount += (line.price_subtotal_without_discount) * (line.discount_amount/ 100)
            if res_config:
                if res_config.tax_discount_policy == 'tax':
                    if order.discount_type == 'line':
                        order.discount_amt = 0.00
                        order.update({
                            #'amount_untaxed': amount_untaxed,
                            #'amount_tax': amount_tax,
                            'tax_amount': amount_tax,
                            #'amount_total': amount_untaxed + amount_tax - line_discount,
                            'amount': amount_untaxed + amount_tax - order.wht_amount,
                            'discount_amt_line' : line_discount,
                        })
                    #elif order.discount_type == 'global':
                        #order.discount_amt_line = 0.00
                        #if order.discount_method == 'per':
                            #order_discount = (amount_untaxed + amount_tax) * (order.discount_amount / 100) 
                            
                            #order.update({
                                ##'amount_untaxed': amount_untaxed,
                                #'tax_amount': amount_tax,
                                #'amount': amount_untaxed + amount_tax - order_discount,
                                #'discount_amt' : order_discount,
                            #})
                        #elif order.discount_method == 'fix':
                            #order_discount = order.discount_amount
                            #order.update({
                                ##'amount_untaxed': amount_untaxed,
                                #'tax_amount': amount_tax,
                                #'amount': amount_untaxed + amount_tax - order_discount,
                                #'discount_amt' : order_discount,
                            #})
                        #else:
                            #order.update({
                                ##'amount_untaxed': amount_untaxed,
                                #'tax_amount': amount_tax,
                                #'amount': amount_untaxed + amount_tax ,
                            #})
                    else:
                        order.update({
                            #'amount_untaxed': amount_untaxed,
                            'tax_amount': amount_tax,
                            'amount': amount_untaxed + amount_tax ,
                            })
                elif res_config.tax_discount_policy == 'untax':
                    if order.discount_type == 'line':
                        order.discount_amt = 0.00
                        #order.tax_amount = amount_tax
                        order.update({
                            #'amount_untaxed': amount_untaxed,
                            'tax_amount': amount_tax,
                            #'tax_amount1': amount_tax,
                            #'amount_total': amount_untaxed + amount_tax - applied_discount,
                            'amount': amount_untaxed + amount_tax - order.wht_amount,
                            #'discount_amt_line' : applied_discount,
                            'discount_amt_line' : line_discount,
                            'amount_price_subtotal_without_discount' : amount_price_subtotal_without_discount,
                            
                        })
                    #elif order.discount_type == 'global':
                        #order.discount_amt_line = 0.00
                        #if order.discount_method == 'per':
                            #order_discount = amount_untaxed * (order.discount_amount / 100)
                            #if order.line_ids:
                                #for line in order.line_ids:
                                    #if line.tax_ids:
                                        #final_discount = 0.0
                                        #try:
                                            #final_discount = ((order.discount_amount*line.price_subtotal)/100.0)
                                        #except ZeroDivisionError:
                                        #    pass
                                        #discount = line.price_subtotal - final_discount
                                        #taxes = line.tax_ids.compute_all(discount, \
                                        #                    order.currency_id,1.0, product=line.product_id, \
                                        #                    partner=order.partner_id)
                                        #sums += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                            #order.update({
                                ##'amount_untaxed': amount_untaxed,
                                #'tax_amount': sums,
                                #'amount': amount_untaxed + sums - order_discount,
                                #'discount_amt' : order_discount,  
                            #})
                        #elif order.discount_method == 'fix':
                            #order_discount = order.discount_amount
                            #if order.line_ids:
                                #for line in order.line_ids:
                                    #if line.tax_ids:
                                        #final_discount = 0.0
                                        #try:
                                            #if amount_untaxed != 0:
                                            #   final_discount = ((order.discount_amount*line.price_subtotal)/amount_untaxed)                                            
                                        #except ZeroDivisionError:
                                        #    pass
                                        #discount = line.price_subtotal - final_discount
                                        #taxes = line.tax_ids._origin.compute_all(discount, \
                                        #                    order.currency_id,1.0, product=line.product_id, \
                                        #                    partner=order.partner_id,)
                                        ## taxes = line.tax_ids.compute_all(discount, \
                                        ##                     order.currency_id,1.0, product=line.product_id, \
                                        ##                     partner=order.partner_id)
                                        #sums += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                            #order.update({
                                ##'amount_untaxed': amount_untaxed,
                                #'tax_amount': sums,
                                #'amount': amount_untaxed + sums - order_discount,
                                #'discount_amt' : order_discount,
                            #})
                        #else:
                            #order.update({
                                ##'amount_untaxed': amount_untaxed,
                                #'tax_amount': amount_tax,
                                #'amount': amount_untaxed + amount_tax ,
                            #})
                    else:
                        order.update({
                            #'amount_untaxed': amount_untaxed,
                            'tax_amount': amount_tax,
                            'amount': amount_untaxed + amount_tax ,
                            })
                else:
                    order.update({
                            #'amount_untaxed': amount_untaxed,
                            'tax_amount': amount_tax,
                            'amount': amount_untaxed + amount_tax ,
                            })         
            else:
                order.update({
                    #'amount_untaxed': amount_untaxed,
                    'tax_amount': amount_tax,
                    'amount': amount_untaxed + amount_tax ,
                    }) 


class account_voucher_line(models.Model):
    _inherit = 'account.voucher.line'
    discount_method = fields.Selection(
            [('fix', 'Fixed'), ('per', 'Percentage')], 'Discount Method')
    discount_type = fields.Selection(related='voucher_id.discount_type', string="Discount Applies to")
    discount_amount = fields.Float('Discount Amount')
    discount_amt = fields.Float('Discount Final Amount')
    #price_subtotal_without_discount = fields.Float(string="Subtotal without Discount" , readonly=True,store=True)
    price_subtotal_without_discount = fields.Float(compute='_compute_amount',string="Subtotal without Discount" , readonly=True,store=True)
    price_tax = fields.Float(string="price_tax" , readonly=True,store=True)
    @api.depends('quantity', 'price_unit', 'tax_ids','discount_method','discount_amount','discount_type','price_subtotal_without_discount')
    def _compute_amount(self):
        for line in self:
            #vals = line._prepare_compute_all_values()
            res_config= self.env.company
            if res_config:
                if res_config.tax_discount_policy == 'untax':
                    if line.discount_type == 'line':
                        if line.discount_method == 'fix':
                            if line.tax_ids:
                                if line.discount_amount:
                                    if line.tax_ids:
                                        if line.price_unit and line.quantity:
                                            taxes_amount_include = 0.0
                                            taxes_amount_execlude = 0.0
                                            for tax_ids in line.tax_ids:
                                                if tax_ids.price_include:
                                                    #not calculate WTH -3 % on PO
                                                    if tax_ids.amount > 0:
                                                        taxes_amount_include = tax_ids.amount
                                                else:
                                                    #not calculate WTH -3 % on PO
                                                    if tax_ids.amount > 0:
                                                        taxes_amount_execlude = tax_ids.amount

                                            cur_obj = self.env['res.currency']
                                            stwd = 0.0
                                            stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))
                                            discount_percent = (line.discount_amount/(line.quantity * stwd))*100
                                            #discount_percent = (line.discount_amount/((line.quantity * line.price_unit)))*100
                                            price_unit_discount = line.price_unit  * (1 - (discount_percent or 0.0) / 100.0)
                                            taxes_res = line.tax_ids.compute_all(price_unit_discount,cur_obj, line.quantity, line.product_id)
                                            #price_unit_wo_discount
                                            line.price_subtotal = stwd - line.discount_amount#taxes_res['total_excluded']
                                            line.price_tax = (line.price_subtotal * (taxes_amount_include/100)) + (line.price_subtotal * (taxes_amount_execlude/100))
                                            #line.price_tax = sum(t.get('amount', 0.0) for t in taxes_res.get('taxes', []))
                                            line.price_subtotal_without_discount =  stwd
                                            #print("-------------------------IN---line.price_tax-------------- " , line.price_tax)
                                    else:
                                        
                                        price = (line.price_unit * line.quantity) - line.discount_amount
                                        #taxes = line.tax_ids.compute_all(price,line.currency_id,1,line.product_id,vals['partner'])
                                        taxes = line.tax_ids.compute_all(price,line.currency_id,1,line.product_id)
                                        line.update({
                                            'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                                            #'price_total': taxes['total_included'] + line.discount_amount,
                                            'price_subtotal': taxes['total_excluded'] + line.discount_amount,
                                            'discount_amt' : line.discount_amount,
                                        })
                                else:
                                    price = (line.price_unit * line.quantity) - line.discount_amount
                                    taxes = line.tax_ids.compute_all(price,line.currency_id,1,line.product_id)
                                    line.update({
                                        'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                                        #'price_total': taxes['total_included'] + line.discount_amount,
                                        'price_subtotal': taxes['total_excluded'] + line.discount_amount,
                                        'discount_amt' : line.discount_amount,
                                    })
                            else:     
                                #case untaxs and fix discount           
                                #price = (vals['price_unit'] * vals['quantity']) - line.discount_amount
                                #taxes = line.tax_ids.compute_all(price,vals['currency_id'],1,vals['product'],vals['partner'])
                                line.price_subtotal = (line.quantity*line.price_unit) - line.discount_amount
                                line.price_subtotal_without_discount =  (line.quantity*line.price_unit)
                                line.price_tax = 0                                 
                                line.update({
                                    #'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                                    #'price_total': taxes['total_included'] + line.discount_amount,
                                    #'price_subtotal': taxes['total_excluded'] + line.discount_amount,
                                    'discount_amt' : line.discount_amount,
                                })
                        elif line.discount_method == 'per':
                            taxes_amount_include = 0.0
                            taxes_amount_execlude = 0.0
                            if line.tax_ids:
                                for tax_ids in line.tax_ids:
                                    if tax_ids.price_include:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_include = tax_ids.amount
                                        if line.discount_amount > 0 :
                                            line.discount_amt = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include)) * line.discount_amount/100                                            
                                    else:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_execlude = tax_ids.amount
                                        if line.discount_amount > 0 :
                                            line.discount_amt = (line.quantity*line.price_unit) * line.discount_amount/100                                            

                            stwd = 0.0
                            stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))                            
                            price = (vals['price_unit'] * vals['quantity']) * (1 - (line.discount_amount or 0.0) / 100.0)
                            #price_x = ((vals['price_unit'] * vals['quantity'])-((vals['price_unit'] * vals['quantity']) * (1 - (line.discount_amount or 0.0) / 100.0)))
                            taxes = line.tax_ids.compute_all(price,vals['currency_id'],1,vals['product'],vals['partner'])
                            if line.discount_amount > 0 :
                                line.discount_amt = (line.quantity*line.price_unit) * line.discount_amount/100
                            line.price_subtotal_without_discount =  stwd
                            line.update({
                                #'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                                #'price_total': taxes['total_included'] + price_x,
                                #'price_subtotal': taxes['total_excluded'] + price_x,
                                #'price_total': taxes['total_included'],
                                'price_subtotal': taxes['total_excluded'],
                                'discount_amt' : line.discount_amt,
                            })
                        else:
                            taxes_amount_include = 0.0
                            taxes_amount_execlude = 0.0
                            cur_obj = self.env['res.currency']
                            if line.tax_ids:
                                for tax_ids in line.tax_ids:
                                    if tax_ids.price_include:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_include = tax_ids.amount
                                    else:
                                        #not calculate WTH -3 % on PO
                                        if tax_ids.amount > 0:
                                            taxes_amount_execlude = tax_ids.amount
                            taxes_res = line.tax_ids.compute_all(line.price_unit,cur_obj, line.quantity, line.product_id)
                            stwd = 0.0
                            stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))
                            line.price_subtotal_without_discount =  stwd
                            line.price_tax = sum(t.get('amount', 0.00000) for t in taxes_res.get('taxes', []))
                            taxes = line.tax_ids.compute_all(line.price_unit,line.currency_id,line.quantity,line.product_id)
                            line.update({
                                #'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                                #'price_total': taxes['total_included'],
                                'price_subtotal': taxes['total_excluded'],
                            })
                    else:
                        
                        #taxes = line.tax_ids.compute_all(line.price_unit,line.currency_id,line.quantity,line.product_id,vals['partner'])
                        taxes = line.tax_ids.compute_all(line.price_unit,line.currency_id,line.quantity,line.product_id)
                        line.update({
                            #'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                            #'price_total': taxes['total_included'],
                            'price_subtotal': taxes['total_excluded'],
                        })
                elif res_config.tax_discount_policy == 'tax':
                    price_x = 0.0
                    if line.discount_type == 'line':
                        taxes = line.tax_ids.compute_all(line.price_unit,line.currency_id,line.quantity,line.product_id)
                        if line.discount_method == 'fix':
                            price_x = (taxes['total_included']) - (taxes['total_included'] - line.discount_amount)
                        elif line.discount_method == 'per':
                            price_x = (taxes['total_included']) - (taxes['total_included'] * (1 - (line.discount_amount or 0.0) / 100.0))                        

                        line.update({
                            #'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                            #'price_total': taxes['total_included'],
                            'price_subtotal': taxes['total_excluded'],
                            'discount_amt' : price_x,
                        })
                    else:
                        taxes = line.tax_ids.compute_all(line.price_unit,line.currency_id,line.quantity,line.product_id)
                        line.update({
                            #'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                            #'price_total': taxes['total_included'],
                            'price_subtotal': taxes['total_excluded'],
                        })
                else:
                    taxes = line.tax_ids.compute_all(line.price_unit,line.currency_id,line.quantity,line.product_id)
                    line.update({
                        #'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                        #'price_total': taxes['total_included'],
                        'price_subtotal': taxes['total_excluded'],
                    })
            else:
                taxes = line.tax_ids.compute_all(line.price_unit,line.currency_id,line.quantity,line.product_id)
                line.update({
                    #'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                    #'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                })

    @api.onchange("quantity","price_unit", 'discount_amount','discount_method','tax_ids')
    def _onchange_purchase_line_ids(self):
        #for order in self.mapped('order_id'):
            #for line in order.line_ids:
            for line in self:
                #line.price_subtotal = (line.quantity*line.price_unit)- line.discount_amount - ((line.quantity*line.price_unit)*line.discount/100)
                if line.discount_method == 'fix':
                        cur_obj = self.env['res.currency']
                        taxes_amount_include = 0.0
                        taxes_amount_execlude = 0.0
                        if line.discount_amount:
                            if line.price_unit and line.quantity:
                                if line.tax_ids:
                                    for tax_ids in line.tax_ids:
                                        if tax_ids.price_include:
                                            #not calculate WTH -3 % on PO
                                            if tax_ids.amount > 0:
                                                taxes_amount_include = tax_ids.amount
                                        else:
                                            #not calculate WTH -3 % on PO
                                            if tax_ids.amount > 0:
                                                taxes_amount_execlude = tax_ids.amount

                                    #discount_percent = line.discount_amount/((line.quantity * line.price_unit) *100 line.discount_amount)
                                    #discount_percent = line.discount_amount/((line.quantity * line.price_unit) *100)
                                    stwd = 0.0
                                    stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))
                                    discount_percent = (line.discount_amount/(line.quantity * stwd))*100
                                    #discount_percent = (line.discount_amount/((line.quantity * line.price_unit)))*100
                                    price_unit_discount = line.price_unit  * (1 - (discount_percent or 0.0) / 100.0)
                                    taxes_res = line.tax_ids.compute_all(price_unit_discount,cur_obj, line.quantity, line.product_id)
                                    #price_unit_wo_discount
                                    line.price_subtotal = stwd - line.discount_amount#taxes_res['total_excluded']
                                    line.price_tax = (line.price_subtotal * (taxes_amount_include/100)) + (line.price_subtotal * (taxes_amount_execlude/100))
                                    line.price_subtotal_without_discount =  stwd

                                else:
                                    line.price_subtotal = (line.quantity*line.price_unit) - line.discount_amount
                                    line.price_subtotal_without_discount =  (line.quantity*line.price_unit)
                                    line.price_tax = 0
                                    #amount_price_subtotal_without_discount += line.price_subtotal_without_discount
                            else: #line.price_unit
                                line.price_subtotal = 0
                                line.price_subtotal_without_discount =  0
                                #amount_price_subtotal_without_discount += line.price_subtotal_without_discount

                        else:    
                            price_unit_discount = line.price_unit 
                            taxes_res = line.tax_ids.compute_all(price_unit_discount,cur_obj, line.quantity, line.product_id)
                            line.price_subtotal = taxes_res['total_excluded']  
                            line.price_subtotal_without_discount =  (line.quantity*line.price_unit)
                            #line.price_tax = sum(t.get('amount', 0.00000) for t in taxes_res.get('taxes', []))              
                elif line.discount_method == 'per':
                        cur_obj = self.env['res.currency']
                        #price_unit_discount = line.price_unit - ((line.price_unit)*line.discount_amount/100)
                        #price_unit_discount = line.price_unit * (1 - (line.discount_amount or 0.0) / 100.0)

                        discount_percent = line.discount_amount
                        price_unit_discount = line.price_unit  * (1 - (discount_percent or 0.0) / 100.0)
                                    
                                    #price_unit_discount = price_unit_discount - line.discount_amount
                        #print("----------------line.discount_method == 'per'----price_unit_discount = " , price_unit_discount)

                                    #price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                                    # new: substract extra_discount
                                    #price -= line.extra_discount
                                    #taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
                                    #line.update({
                                        #'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                                        #'price_total': taxes['total_included'],
                                        #'price_subtotal': taxes['total_excluded'],
                                    #})
                        #print("----------------line.discount_method == 'per'----price_unit_discount = " , price_unit_discount) 
                        taxes_amount_include = 0.0
                        taxes_amount_execlude = 0.0
                        
                        if line.tax_ids:
                            for tax_ids in line.tax_ids:
                                if tax_ids.price_include:
                                    #not calculate WTH -3 % on PO
                                    if tax_ids.amount > 0:
                                        taxes_amount_include = tax_ids.amount
                                    if line.discount_amount > 0 :
                                        line.discount_amt = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include)) * line.discount_amount/100                                            
                                else:
                                    #not calculate WTH -3 % on PO
                                    if tax_ids.amount > 0:
                                        taxes_amount_execlude = tax_ids.amount
                                    if line.discount_amount > 0 :
                                        line.discount_amt = (line.quantity*line.price_unit) * line.discount_amount/100                                            

                        stwd = 0.0
                        stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))

                        taxes_res = line.tax_ids.compute_all(price_unit_discount,cur_obj, line.quantity, line.product_id)
                        #print("----------------line.discount_method == 'per'----taxes_res = " , taxes_res) 
                        line.price_subtotal = taxes_res['total_excluded']
                        line.price_tax = sum(t.get('amount', 0.00000) for t in taxes_res.get('taxes', []))     
                        line.price_subtotal_without_discount =  (line.quantity*line.price_unit)
                        line.price_subtotal_without_discount =  stwd
                        #if line.discount_amount > 0 :
                            #line.discount_amt = (line.quantity*line.price_unit) * line.discount_amount/100
                else:
                        taxes_amount_include = 0.0
                        taxes_amount_execlude = 0.0
                        cur_obj = self.env['res.currency']
                        if line.tax_ids:
                            
                            for tax_ids in line.tax_ids:
                                if tax_ids.price_include:
                                    #not calculate WTH -3 % on PO
                                    if tax_ids.amount > 0:
                                        taxes_amount_include = tax_ids.amount
                                else:
                                    #not calculate WTH -3 % on PO
                                    if tax_ids.amount > 0:
                                        taxes_amount_execlude = tax_ids.amount
                        taxes_res = line.tax_ids.compute_all(line.price_unit,cur_obj, line.quantity, line.product_id)
                        stwd = 0.0
                        stwd = (line.price_unit * line.quantity) * (100/(100+taxes_amount_include))
                        line.price_subtotal_without_discount =  stwd
                        line.price_tax = sum(t.get('amount', 0.00000) for t in taxes_res.get('taxes', []))





