# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

from odoo import models, fields, api, _

class account_invoice(models.Model):
    _inherit = "account.move"
    
    def _prepare_invoice_line_from_po_line(self, line):
        res = super(account_invoice,self)._prepare_invoice_line_from_po_line(line)
        print ("res=======",res)
        if line.second_uom_id and line.second_uom_qty:
            res.update({
                'second_uom_id':line.second_uom_id and line.second_uom_id.id or False,
                'second_uom_qty':line.second_uom_qty or 0.0,
            })
        return res
        
        
    
    
class account_invoice_line(models.Model):
    _inherit = "account.move.line"
    
    uom_category_id = fields.Many2one('uom.category', related='product_uom_id.category_id', string='UOM Category')
    second_uom_id = fields.Many2one('uom.uom',string="Secondary UOM")
    second_uom_qty = fields.Float('Secondary Qty')
    second_price = fields.Float('Second Price')
    
    @api.onchange('second_price','product_uom_id','second_uom_id')
    def onchange_second_price_unit(self):
        if self.second_uom_id and self.product_uom_id and self.second_price:
            if self.second_uom_id.id == self.product_uom_id.id:
                self.price_unit = self.second_price
            else:
                if self.product_uom_id.uom_type == 'smaller':
                    self.price_unit = self.second_price / self.product_uom_id.factor
                elif self.product_uom_id.uom_type == 'bigger':
                    self.price_unit = self.second_price * self.product_uom_id.factor_inv
                else:
                    if self.second_uom_id.uom_type == 'smaller':
                        self.price_unit = self.second_price * self.second_uom_id.factor
                    elif self.second_uom_id.uom_type == 'bigger':
                        self.price_unit = self.second_price / self.second_uom_id.factor_inv
                    else:
                        self.price_unit = self.second_price
                    
                    
    
    @api.onchange('price_unit','uom_id','second_uom_id')
    def onchange_dev_price_unit(self):
        if self.second_uom_id and self.product_uom_id:
            if self.second_uom_id.id == self.product_uom_id.id:
                self.second_price = self.price_unit
            else:
                if self.second_uom_id.uom_type == 'smaller':
                    self.second_price = self.price_unit / self.second_uom_id.factor
                elif self.second_uom_id.uom_type == 'bigger':
                    self.second_price = self.price_unit * self.second_uom_id.factor_inv
                else:
                    if self.product_uom_id.uom_type == 'smaller':
                        self.second_price = self.price_unit * self.uom_id.factor
                    elif self.product_uom_id.uom_type == 'bigger':
                        self.second_price = self.price_unit / self.product_uom_id.factor_inv
                    else:
                        self.second_price = self.price_unit
                        
                        
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        res = super(account_invoice_line,self)._onchange_product_id()
        if self.product_id:
            self.second_uom_id = self.product_id.second_uom_id and self.product_id.second_uom_id.id or False
            if self.second_uom_id:
                self.second_uom_qty = self.product_uom_id._compute_quantity(self.quantity, self.second_uom_id)
        return res
    
    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        res = super(account_invoice_line,self)._onchange_uom_id()
        if self.second_uom_id:
            self.second_uom_qty = self.product_uom_id._compute_quantity(self.quantity, self.second_uom_id)
        return res
    
    @api.onchange('quantity')
    def _onchange_product_qunatity(self):
        if self.second_uom_id:
            self.second_uom_qty = self.product_uom_id._compute_quantity(self.quantity, self.second_uom_id)
        
    
    @api.onchange('second_uom_id','second_uom_qty')
    def onchange_dev_product_id(self):
        if self.product_id and self.second_uom_id and self.product_uom_id:
            if self.second_uom_id:
                self.quantity = self.second_uom_id._compute_quantity(self.second_uom_qty, self.product_uom_id)
    
    
    
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
