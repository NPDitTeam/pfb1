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

class purchase_order_line(models.Model):
    _inherit = "purchase.order.line"
    
    uom_category_id = fields.Many2one('uom.category', related='product_uom.category_id', string='UOM Category')
    second_uom_id = fields.Many2one('uom.uom',string="Secondary UOM")
    second_uom_qty = fields.Float('Secondary Qty')
    second_price = fields.Float('Second Price')
    
    
    @api.onchange('second_price','product_uom','second_uom_id')
    def onchange_second_price_unit(self):
        if self.second_uom_id and self.product_uom and self.second_price:
            if self.second_uom_id.id == self.product_uom.id:
                self.price_unit = self.second_price
            else:
                if self.product_uom.uom_type == 'smaller':
                    self.price_unit = self.second_price / self.product_uom.factor
                elif self.product_uom.uom_type == 'bigger':
                    self.price_unit = self.second_price * self.product_uom.factor_inv
                else:
                    if self.second_uom_id.uom_type == 'smaller':
                        self.price_unit = self.second_price * self.second_uom_id.factor
                    elif self.second_uom_id.uom_type == 'bigger':
                        self.price_unit = self.second_price / self.second_uom_id.factor_inv
                    else:
                        self.price_unit = self.second_price
                    
                    
    
    @api.onchange('price_unit','product_uom','second_uom_id')
    def onchange_dev_price_unit(self):
        if self.second_uom_id and self.product_uom:
            if self.second_uom_id.id == self.product_uom.id:
                self.second_price = self.price_unit
            else:
                if self.second_uom_id.uom_type == 'smaller':
                    self.second_price = self.price_unit / self.second_uom_id.factor
                elif self.second_uom_id.uom_type == 'bigger':
                    self.second_price = self.price_unit * self.second_uom_id.factor_inv
                else:
                    if self.product_uom.uom_type == 'smaller':
                        self.second_price = self.price_unit * self.product_uom.factor
                    elif self.product_uom.uom_type == 'bigger':
                        self.second_price = self.price_unit / self.product_uom.factor_inv
                    else:
                        self.second_price = self.price_unit
                        
                        
    
    @api.onchange('product_id')
    def onchange_product_id(self):
        res = super(purchase_order_line,self).onchange_product_id()
        if self.product_id:
            self.second_uom_id = self.product_id.second_uom_id and self.product_id.second_uom_id.id or False
            if self.second_uom_id:
                self.second_uom_qty = self.product_uom._compute_quantity(self.product_qty, self.second_uom_id)
        return res
    
    
    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        res = super(purchase_order_line,self)._onchange_quantity()
        if self.second_uom_id:
            self.second_uom_qty = self.product_uom._compute_quantity(self.product_qty, self.second_uom_id)
        return res

    @api.onchange('second_uom_id','second_uom_qty')
    def onchange_dev_second_quantity(self):
        if self.product_id and self.second_uom_id and self.product_uom:
            if self.second_uom_id:
                self.product_qty = self.second_uom_id._compute_quantity(self.second_uom_qty, self.product_uom)

    def _prepare_account_move_line(self):
        res = super(purchase_order_line,self)._prepare_account_move_line()
        if self.second_uom_id and self.second_uom_qty:
            res.update({
                'second_uom_id':self.second_uom_id and self.second_uom_id.id or False,
                'second_uom_qty':self.second_uom_qty or 0.0,
            })
        return res
        


    
    def _prepare_stock_moves(self, picking):
        res = super(purchase_order_line,self)._prepare_stock_moves(picking)
        if self.second_uom_id and self.second_uom_qty:
            uom_id = self.env['uom.uom'].browse(res[0].get('product_uom'))
            second_uom_qty = uom_id._compute_quantity(res[0].get('product_uom_qty'), self.second_uom_id)
            res[0].update({
                'second_uom_id':self.second_uom_id and self.second_uom_id.id or False,
                'second_uom_qty':second_uom_qty,
            })
        
        return res
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
